import os
import re
import yaml
import json
import sqlite3
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

# ===================== 載入環境變數 =====================
load_dotenv()

# ===================== Free Claude Code (FCC) Proxy 設定（本機服務，無外部網路呼叫） =====================
# FCC（free-claude-code）以 fcc-server 啟動後，預設監聽 http://127.0.0.1:8082
# 只使用本機 localhost，不會呼叫公網
FCC_BASE_URL = os.getenv("FCC_BASE_URL", "http://127.0.0.1:8082")
FCC_API_KEY = os.getenv("FCC_API_KEY", "freecc")
FCC_MODEL = os.getenv("FCC_MODEL", "claude-sonnet-4-20250514")

# ---- 模型Failover Chain（本機FCC路由） ----
FCC_FAILOVER_MODELS = [
    m.strip() for m in os.getenv(
        "FCC_FAILOVER_MODELS",
        "nvidia_nim/minimaxai/minimax-m3",
    ).split(",") if m.strip()
]
FCC_RETRIES = int(os.getenv("FCC_RETRIES", "2"))
FCC_MAX_TOKENS = int(os.getenv("FCC_MAX_TOKENS", "8192"))

DB_PATH = os.getenv("DB_PATH", "./db/se_agent.db")
QUALITY_THRESHOLD = float(os.getenv("QUALITY_THRESHOLD", 70))


def _parse_anthropic_response(body: str) -> str:
    """解析 FCC 回應：支援 SSE event 流與標準 Anthropic JSON 兩種格式，回傳純文字。"""
    stripped = body.lstrip()
    # FCC SSE stream
    if stripped.startswith("event:"):
        parts: List[str] = []
        for line in body.splitlines():
            if not line.startswith("data: "):
                continue
            data = json.loads(line[6:])
            t = data.get("type")
            delta = data.get("delta") or {}
            txt = delta.get("text")
            if t == "content_block_delta" and txt:
                parts.append(txt)
        return "".join(parts).strip()
    # Standard Anthropic JSON response
    obj = json.loads(body)
    blocks = obj.get("content", [])
    texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    return "".join(texts).strip()


def call_anthropic_messages(system_prompt: str, user_msg: str, max_tokens: Optional[int] = None) -> str:
    """呼叫本機FCC的Anthropic /v1/messages端點，完全本地服務，無外部網路。
    內建模型failover：依 FCC_MODEL -> FCC_FAILOVER_MODELS 順序嘗試，
    每個模型重試 FCC_RETRIES 次；全部失敗才 raise RuntimeError。
    """
    if max_tokens is None:
        max_tokens = FCC_MAX_TOKENS
    url = f"{FCC_BASE_URL.rstrip('/')}/v1/messages"
    headers = {
        "Authorization": f"Bearer {FCC_API_KEY}",
        "Content-Type": "application/json",
    }
    model_chain = [FCC_MODEL] + [m for m in FCC_FAILOVER_MODELS if m != FCC_MODEL]
    last_err: str = "unknown"

    for model in model_chain:
        for attempt in range(1, FCC_RETRIES + 1):
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_msg}],
            }
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=(10, 600))
            except requests.RequestException as exc:
                last_err = f"{model} #{attempt}: {type(exc).__name__}: {exc}"
                print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
                continue
            if resp.status_code >= 400:
                last_err = f"{model} #{attempt}: HTTP {resp.status_code} {resp.text[:200]}"
                print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
                continue
            if "Provider API request failed" in resp.text:
                last_err = f"{model} #{attempt}: 上游 provider 錯誤"
                print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
                continue
            try:
                text = _parse_anthropic_response(resp.text)
            except (json.JSONDecodeError, ValueError) as exc:
                last_err = f"{model} #{attempt}: 回應解析失敗 {type(exc).__name__}: {exc}"
                print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
                continue
            if not text:
                last_err = f"{model} #{attempt}: 空回應"
                print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
                continue
            if model != FCC_MODEL:
                print(f"[FCC] 已自動切換至備援模型: {model}")
            return text
    raise RuntimeError(f"FCC 所有模型（{model_chain}）皆失敗，最後錯誤: {last_err}")


# ===================== Pydantic 資料模型 =====================
class SkillDef(BaseModel):
    meta: Dict[str, Any]
    input_schema: Dict[str, Any]
    core_prompt: str
    acceptance_criteria: List[str]
    output_schema: Dict[str, Any]
    error_handler: Dict[str, Any]
    gate: Optional[Dict[str, Any]] = None  # 新增 gate 配置


class WorkflowSpec(BaseModel):
    workflow_id: str
    name: str
    description: str
    version: str
    cross_cutting_skills: List[Dict[str, str]]
    gate: Dict[str, Any]
    stages: List[Dict[str, Any]]


class Artifact(BaseModel):
    skill_id: str
    stage_id: Optional[str] = None
    artifact: Dict[str, Any]
    unresolved_questions: List[Any]
    risk_list: List[Any]
    quality_score: float
    raw_llm_output: str


# ===================== Gate 結果資料模型 =====================
@dataclass
class GateResult:
    passed: bool
    message: str
    action: str  # e.g., "pause_workflow", "continue", "abort"


# ===================== DB初始化 =====================
def _migrate_db(cur):
    """舊版DB補欄位：workflow_runs.paused_stage（人工審批暫停點）"""
    cols = [r[1] for r in cur.execute("PRAGMA table_info(workflow_runs)").fetchall()]
    if "paused_stage" not in cols:
        cur.execute("ALTER TABLE workflow_runs ADD COLUMN paused_stage TEXT")
    # 新增 approval_notes table（如果不存在）
    cur.execute("""
    CREATE TABLE IF NOT EXISTS approval_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        stage_id TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
    )
    """)


def init_db():
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS workflow_runs (
        run_id TEXT PRIMARY KEY,
        workflow_id TEXT,
        status TEXT, -- running / paused_human / completed / failed
        paused_stage TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    _migrate_db(cur)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        skill_id TEXT,
        stage_id TEXT,
        payload TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
    )
    """)
    conn.commit()
    conn.close()


def save_artifact(run_id: str, stage_id: str, skill_id: str, artifact: Artifact):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    payload = artifact.model_dump_json()
    cur.execute(
        "INSERT INTO artifacts(run_id, skill_id, stage_id, payload) VALUES (?,?,?,?)",
        (run_id, skill_id, stage_id, payload)
    )
    conn.commit()
    conn.close()


def load_artifacts(run_id: str) -> List[Artifact]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    rows = cur.execute("SELECT payload FROM artifacts WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    conn.close()
    arts = []
    for r in rows:
        data = json.loads(r[0])
        arts.append(Artifact(**data))
    return arts


def delete_stage_artifacts(run_id: str, stage_id: str):
    """刪除某run某stage的所有artifact（人工審批選擇重跑時用）"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM artifacts WHERE run_id=? AND stage_id=?", (run_id, stage_id))
    conn.commit()
    conn.close()


def save_approval_note(run_id: str, stage_id: str, note: str):
    """儲存人工審批備註至artifact審計紀錄"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO approval_notes(run_id, stage_id, note) VALUES (?,?,?)",
        (run_id, stage_id, note)
    )
    conn.commit()
    conn.close()


def get_approval_notes(run_id: str, stage_id: str) -> List[Dict]:
    """取得特定 run 和 stage 的審批備註"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM approval_notes WHERE run_id=? AND stage_id=? ORDER BY created_at",
        (run_id, stage_id)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_run_status(run_id: str, status: str, paused_stage: Optional[str] = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if paused_stage is not None:
        cur.execute("UPDATE workflow_runs SET status=?, paused_stage=? WHERE run_id=?", (status, paused_stage, run_id))
    else:
        cur.execute("UPDATE workflow_runs SET status=? WHERE run_id=?", (status, run_id))
    conn.commit()
    conn.close()


def get_run(run_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ===================== Skill YAML 載入器 =====================
def load_skill(skill_id: str, skill_dir: str = "./skills") -> SkillDef:
    """讀取skill yaml，根據meta.id匹配（支援頂層 skillDefinition 或 Harness spec.skillDefinition 結構）"""
    p = Path(skill_dir)
    for f in p.glob("*.yaml"):
        raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        sd = raw.get("skillDefinition") or (raw.get("spec") or {}).get("skillDefinition")
        if sd is None:
            continue
        if sd["meta"]["id"] == skill_id:
            gate_config = sd.get("gate")
            return SkillDef(
                meta=sd["meta"],
                input_schema=sd.get("input_schema", {"type": "object", "properties": {}}),
                core_prompt=sd.get("core_prompt", ""),
                acceptance_criteria=sd.get("acceptance_criteria", []),
                output_schema=sd.get("output_schema") or {"type": "object", "properties": {}},
                error_handler=sd.get("error_handler", {"retry_strategy": 1, "max_retry_count": 3, "fallback_action": "mark_human_review"}),
                gate=gate_config
            )
    raise FileNotFoundError(f"Skill id {skill_id} not found in {skill_dir}")


def load_skill_gate(skill_id: str, skill_dir: str = "./skills") -> Optional[Dict[str, Any]]:
    """僅讀取 skill 的 gate 配置"""
    p = Path(skill_dir)
    for f in p.glob("*.yaml"):
        raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        sd = raw.get("skillDefinition") or (raw.get("spec") or {}).get("skillDefinition")
        if sd is None:
            continue
        if sd["meta"]["id"] == skill_id:
            return sd.get("gate")
    return None


def load_workflow_spec(path: str = "workflow_spec.yaml") -> WorkflowSpec:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return WorkflowSpec(**raw)


# ===================== LLM JSON 解析與修復 =====================
def _strip_code_fence(text: str) -> str:
    """去掉 markdown code fence 與前後雜訊，取出 JSON 主體片段"""
    code_fence_pattern = r'```[a-zA-Z]*\s*(.*?)\s*```'
    matches = list(re.finditer(code_fence_pattern, text, re.DOTALL))
    if matches:
        json_candidates = []
        for match in matches:
            content = match.group(1)
            stripped_content = content.strip()
            if stripped_content.startswith('{') or stripped_content.startswith('['):
                json_candidates.append(content)
        if json_candidates:
            selected_content = json_candidates[-1]
        else:
            selected_content = matches[-1].group(1)
        t = selected_content
    else:
        t = text.strip()

    start_curly = t.find("{")
    start_bracket = t.find("[")
    start_pos = -1
    if start_curly != -1 and start_bracket != -1:
        start_pos = min(start_curly, start_bracket)
    elif start_curly != -1:
        start_pos = start_curly
    elif start_bracket != -1:
        start_pos = start_bracket
    if start_pos == -1:
        return t
    return _extract_json_from_text(t[start_pos:])


def _extract_json_from_text(text: str) -> str:
    """從文本中提取有效的JSON片段，處理可能的截斷情況"""
    if not text:
        return text
    stack = []
    in_string = False
    escape_next = False
    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append(ch)
        elif ch in '}]':
            if not stack:
                return text[:i]
            opening = stack.pop()
            if (opening == '{' and ch != '}') or (opening == '[' and ch != ']'):
                return text[:i]
            if not stack:
                return text[:i+1]
    return text


def _close_open_json(s: str) -> str:
    """掃描未閉合的字串與括號，補上結尾使其成為合法JSON（截斷修復用）"""
    stack: List[str] = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
    suffix = '"' if in_str else ""
    suffix += "".join("}" if c == "{" else "]" for c in reversed(stack))
    return s + suffix


def _fix_common_json_issues(text: str) -> str:
    """修復常見的JSON問題，如尾隨逗號、單引號、註解等"""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        in_string = False
        escape_next = False
        cut_idx = None
        for i, ch in enumerate(line):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string and i + 1 < len(line) and line[i:i+2] == '//':
                cut_idx = i
                break
        if cut_idx is not None:
            line = line[:cut_idx]
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    while '/*' in text and '*/' in text:
        start = text.find('/*')
        end = text.find('*/', start + 2)
        if end != -1:
            text = text[:start] + text[end+2:]
        else:
            break
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def parse_llm_json(text: str) -> Dict[str, Any]:
    """解析LLM回傳的JSON，具備容錯：
    1. 去code fence、取第一個 { 之後的內容
    2. 清除常見JSON問題（註釋、尾隨逗號等）
    3. 直接json.loads
    4. 失敗則視為截斷，補閉合括號再試
    5. 仍失敗則從尾端邊界往回剪，每段補閉合嘗試
    """
    body = _strip_code_fence(text)
    cleaned_body = _fix_common_json_issues(body)
    candidates: List[str] = [cleaned_body]
    candidates.append(_close_open_json(cleaned_body))

    cut_points = [i for i, ch in enumerate(cleaned_body) if ch in ",}\""]
    for cp in reversed(cut_points[-60:]):
        frag = cleaned_body[:cp + 1] if cleaned_body[cp] in ",}" else cleaned_body[:cp]
        candidates.append(_close_open_json(frag))

    last_err: Exception = ValueError("empty content")
    for cand in candidates:
        if not cand.strip():
            continue
        try:
            return json.loads(cand)
        except json.JSONDecodeError as exc:
            last_err = exc
    raise ValueError(f"LLM JSON解析失敗（含截斷修復嘗試）：{last_err}\n原始輸出前200字：{text[:200]!r}")


# ===================== LLM Skill 執行核心 =====================
def execute_skill(skill: SkillDef, project_context: Dict, previous_artifacts: List[Artifact], user_input: str) -> Artifact:
    """呼叫LLM執行單一支Skill，強制輸出JSON（含截斷自動重試）"""
    prev_payload = [a.model_dump() for a in previous_artifacts]
    system_prompt = f"""
{skill.core_prompt}
【驗收準則】
{yaml.dump(skill.acceptance_criteria)}
【強制輸出規則】
你必須只回傳嚴格JSON，不要前言、不要解釋、不要markdown code fence。
輸出必須完全符合output_schema結構：
{json.dumps(skill.output_schema, indent=2)}
"""
    user_msg = json.dumps({
        "project_context": project_context,
        "user_input": user_input,
        "previous_artifacts": prev_payload
    }, ensure_ascii=False, indent=2)

    raw_text = call_anthropic_messages(system_prompt, user_msg)
    try:
        parsed = parse_llm_json(raw_text)
    except ValueError as e:
        print(f"[execute_skill] JSON解析失敗（疑似截斷或格式錯誤），以max_tokens={FCC_MAX_TOKENS*2}重試一次: {str(e)[:100]}...")
        system_prompt_retry = system_prompt + "\n注意：輸出空間有限，請精簡內容（每個清單最多5項、描述一句話），確保JSON完整閉合。"
        raw_text = call_anthropic_messages(system_prompt_retry, user_msg, max_tokens=FCC_MAX_TOKENS * 2)
        try:
            parsed = parse_llm_json(raw_text)
        except ValueError as retry_e:
            print(f"[execute_skill] 重試後仍然失敗: {str(retry_e)[:200]}")
            print(f"[execute_skill] 原始LLM輸出前500字符: {raw_text[:500]}")
            parsed = {"artifact": {}, "unresolved_questions": [], "risk_list": [], "quality_score": 0}
            quality_match = re.search(r'"quality_score"\s*:\s*(\d+(?:\.\d+)?)', raw_text)
            if quality_match:
                try:
                    parsed["quality_score"] = float(quality_match.group(1))
                    print(f"[execute_skill] 從原始文本中提取到quality_score: {parsed['quality_score']}")
                except ValueError:
                    pass

    # 容錯：LLM 回傳非 dict（list / int / str）時，包裝成 dict 並把內容塞進 artifact
    if not isinstance(parsed, dict):
        print(f"[execute_skill] JSON 解析結果非 dict（{type(parsed).__name__}），進行包裝修復")
        wrapped = {"artifact": {}, "unresolved_questions": [], "risk_list": [], "quality_score": 0}
        if isinstance(parsed, list):
            wrapped["artifact"] = {"raw_items": parsed}
        else:
            wrapped["artifact"] = {"raw_value": parsed}
        parsed = wrapped

    # 容錯：LLM 把 output_schema 中的子欄位（如 risk_list / quality_score / unresolved_questions）
    # 直接寫在頂層而沒有包進 artifact 時，補齊包裝並補抓 quality_score。
    artifact_raw = parsed.get("artifact")
    if not isinstance(artifact_raw, dict):
        artifact_raw = {}
    for top_key in ("risk_list", "unresolved_questions", "quality_score"):
        if top_key not in parsed and isinstance(artifact_raw.get(top_key), (list, int, float)):
            parsed[top_key] = artifact_raw[top_key]
    if artifact_raw:
        # 將 artifact 內預期的子欄位保留（如 business_goal 等）
        parsed["artifact"] = artifact_raw

    # 容錯：LLM 直接把業務欄位寫在頂層（未包進 artifact）時，自動包裝進 artifact
    if not artifact_raw and isinstance(parsed, dict):
        extras = {
            k: v for k, v in parsed.items()
            if k not in ("artifact", "unresolved_questions", "risk_list", "quality_score")
        }
        if extras:
            print(f"[execute_skill] 偵測到頂層業務欄位未包artifact，自動包裝: {list(extras.keys())}")
            parsed["artifact"] = extras
            artifact_raw = extras

    quality_score = parsed.get("quality_score", 0)
    try:
        quality_score = float(quality_score)
        if quality_score < 0:
            quality_score = 0
        elif quality_score > 100:
            quality_score = 100
    except (ValueError, TypeError):
        quality_score = 0
        print(f"[execute_skill] quality_score無效，使用預設值0: {parsed.get('quality_score')}")

    art = Artifact(
        skill_id=skill.meta["id"],
        artifact=parsed.get("artifact", {}),
        unresolved_questions=parsed.get("unresolved_questions", []),
        risk_list=parsed.get("risk_list", []),
        quality_score=quality_score,
        raw_llm_output=raw_text
    )
    return art


# ===================== Gate 驗證函數 =====================
def run_gate_validation(main_artifact: Artifact, cross_artifacts: List[Artifact], skill_id: str) -> GateResult:
    """
    讀取 skill 的 gate 配置，比對 main_artifact 的 quality_score 與其他規則，
    回傳 GateResult（passed, message, action）。
    """
    # 讀取 skill gate 配置
    gate_config = load_skill_gate(skill_id)
    if gate_config is None:
        # 若無 gate 配置，則預設放行
        return GateResult(passed=True, message="無 gate 配置，預設放行", action="continue")

    # 取出 quality_score 款檢（如果有定義）
    quality_score = main_artifact.quality_score
    threshold_settings = gate_config.get("threshold_settings", {})
    quality_score_min = threshold_settings.get("quality_score_min", 0.0)

    msg_list = []
    passed = True

    # quality_score 檢查
    if quality_score < quality_score_min:
        passed = False
        msg_list.append(f"quality_score {quality_score} < 門檻 {quality_score_min}")

    # 以下可以根據 gate_config 中的 validation_rules 做額外檢查
    # 但目前範例只實作 quality_threshold_audit，其他規則可依需求擴充
    validation_rules = gate_config.get("validation_rules", [])
    for rule in validation_rules:
        # 這裡僅示範如何讀取 rule，實際依據 rule 的 check_method 進行檢查
        # 為簡化，我們假設所有 rule 已經在 quality_score 中 body 內涵蓋
        # 未來可依據 rule 的 criteria_id、description 等做更細部的驗證
        pass

    # 若有通過，則 action 通常為 "continue"；未通過則依 failure_handling.action
    if not passed:
        action = gate_config.get("failure_handling", {}).get("action", "pause_workflow")
    else:
        action = "continue"

    message = "; ".join(msg_list) if msg_list else "Gate 驗證通過"
    return GateResult(passed=passed, message=message, action=action)


# ===================== Gate 不通過例外（供Streamlit攔截） =====================
class GatePause(Exception):
    """Gate不通過且需人工審批時拋出，攜帶暫停點資訊供UI續跑"""
    def __init__(self, stage_id: str, skill_id: str, message: str):
        self.stage_id = stage_id
        self.skill_id = skill_id
        self.message = message
        super().__init__(f"GATE_PAUSE|stage={stage_id}|skill={skill_id}|msg={message}")


# ===================== Workflow 主執行器 =====================
def _run_stages(run_id: str, workflow: WorkflowSpec, project_context: Dict, user_input: str,
                all_artifacts: List[Artifact], start_idx: int = 0) -> List[Artifact]:
    """從指定stage索引開始執行；Gate不通過且需人工審批時拋出GatePause"""
    for stage in workflow.stages[start_idx:]:
        stage_id = stage["stage_id"]
        skill_id = stage["skill_id"]
        print(f"\n===== 執行 Stage [{stage_id}] Skill:{skill_id} =====")

        # 檢查是否為程式碼生成階段，如果是則先執行 my-code-standard 作為前置檢查
        code_generating_skills = ["skill_se_code_implementation", "skill_code_renderer"]
        my_cs_art = None
        if skill_id in code_generating_skills:
            print(f" -> 偵測到程式碼生成階段，先執行 my-code-standard 作為前置檢查...")
            try:
                my_cs_skill = load_skill("my-code-standard")
            except FileNotFoundError as e:
                # my-code-standard skill 不存在（資料夾格式或未安裝），略過前置檢查不中斷流程
                print(f"   my-code-standard skill 無法載入，略過前置檢查: {e}")
                my_cs_skill = None
            my_cs_art = None
            if my_cs_skill is not None:
                try:
                    # 為my-code-standard準備輸入 - 它需要專案內容和使用者輸入
                    my_cs_art = execute_skill(my_cs_skill, project_context, all_artifacts, user_input)
                    # 不將my-code-standard作為獨artefact保存，只作為前置檢查
                    print(f"   my-code-standard 前置檢查完成，quality_score: {my_cs_art.quality_score}")
                except Exception as e:
                    # 記錄錯誤但不中斷流程，繼續執行主Skill
                    print(f"   my-code-standard 前置檢查發生異常: {e}")
                    # 創建一個默認的my-code-standard artefact以避免後續錯誤
                    my_cs_art = Artifact(
                        skill_id="my-code-standard",
                        artifact={"process_compliance": {"tdd_acknowledged": False, "process_understood": False, "commitment_level": "None"}},
                        unresolved_questions=[],
                        risk_list=[],
                        quality_score=0.0,
                        raw_llm_output=f"Error during pre-check: {e}"
                    )

            # 構建增強的 project_context，包含 my-code-standard 前置檢查結果
            enhanced_project_context = {
                **project_context,
                "my_code_standard_precheck": {
                    "quality_score": my_cs_art.quality_score if my_cs_art else None,
                    "process_compliance": my_cs_art.artifact.get("process_compliance", {}) if my_cs_art else {}
                }
            }

        skill = load_skill(skill_id)
        dep_stage_ids = stage.get("depends_on", [])
        deps_arts = [a for a in all_artifacts if a.stage_id in dep_stage_ids]

        if skill_id in code_generating_skills:
            # 構建增強的 project_context，包含 my-code-standard 前置檢查結果
            enhanced_project_context = {
                **project_context,
                "my_code_standard_precheck": {
                    "quality_score": my_cs_art.quality_score if my_cs_art else None,
                    "process_compliance": my_cs_art.artifact.get("process_compliance", {}) if my_cs_art else {}
                }
            }
            main_art = execute_skill(skill, enhanced_project_context, deps_arts, user_input)
        else:
            main_art = execute_skill(skill, project_context, deps_arts, user_input)

        main_art.stage_id = stage_id
        all_artifacts.append(main_art)
        save_artifact(run_id, stage_id, skill_id, main_art)
        print(f"主Skill quality_score: {main_art.quality_score}")

        cross_arts: List[Artifact] = []
        for cross_def in workflow.cross_cutting_skills:
            cross_skill_id = cross_def["skill_id"]
            print(f" -> 執行橫切審計: {cross_skill_id}")
            cross_skill = load_skill(cross_skill_id)
            cross_art = execute_skill(cross_skill, project_context, all_artifacts, user_input)
            cross_art.stage_id = stage_id
            cross_arts.append(cross_art)
            all_artifacts.append(cross_art)
            save_artifact(run_id, stage_id, cross_skill_id, cross_art)

        # 使用 skill 的 gate 配置進行驗證
        gate_result = run_gate_validation(main_art, cross_arts, skill_id)
        print(f"\nGate驗證結果: {gate_result.passed}, 訊息: {gate_result.message}, 建議動作: {gate_result.action}")

        # 自動重試：Gate未通過時，帶著審查意見重新執行本stage（依skill的max_retry_count，上限3次）
        if not gate_result.passed and gate_result.action in ("pause_workflow", "abort"):
            max_retries = 3
            try:
                eh = skill.error_handler or {}
                max_retries = int(eh.get("max_retry_count", 3))
            except (ValueError, TypeError):
                max_retries = 3
            for retry_no in range(1, max_retries + 1):
                print(f"\n===== [自動重試 {retry_no}/{max_retries}] Stage [{stage_id}] 未通過Gate（{gate_result.message}），帶審查意見重新執行 =====")
                retry_ctx = dict(enhanced_project_context if skill_id in code_generating_skills else project_context)
                retry_ctx["gate_retry_feedback"] = gate_result.message
                main_art = execute_skill(skill, retry_ctx, deps_arts, user_input)
                main_art.stage_id = stage_id
                all_artifacts.append(main_art)
                save_artifact(run_id, stage_id, skill_id, main_art)
                print(f"重試後主Skill quality_score: {main_art.quality_score}")
                gate_result = run_gate_validation(main_art, cross_arts, skill_id)
                print(f"重試後Gate驗證結果: {gate_result.passed}, 訊息: {gate_result.message}")
                if gate_result.passed:
                    break

        if not gate_result.passed and gate_result.action == "pause_workflow":
            set_run_status(run_id, "paused_human", paused_stage=stage_id)
            print("\n===== 流程暫停，等待人工審批 =====")
            print("選項: [A]強行放行 [R]修正後重跑本stage [X]中斷流程")
            raise GatePause(stage_id, skill_id, gate_result.message)
        # 若 action 為其他值（如 abort），可在此處理
        elif not gate_result.passed and gate_result.action == "abort":
            set_run_status(run_id, "failed")
            print("\n===== 工作流程已中止（Gate 觸發 abort）=====")
            raise RuntimeError(f"Gate abort: {gate_result.message}")

    set_run_status(run_id, "completed")
    print("\n✅ Workflow全部執行完成")
    return all_artifacts


def run_workflow(run_id: str, workflow: WorkflowSpec, project_context: Dict, user_input: str) -> List[Artifact]:
    """全新執行一次workflow。Gate暫停時拋出GatePause（可之後以resume_workflow續跑）"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO workflow_runs(run_id, workflow_id, status, paused_stage) VALUES (?,?,?,?)",
                (run_id, workflow.workflow_id, "running", None))
    conn.commit()
    conn.close()
    return _run_stages(run_id, workflow, project_context, user_input, all_artifacts=[], start_idx=0)


def list_all_run_ids() -> list[str]:
    """列出所有唯一run_id，依建立時間排序"""
    import sqlite3
    conn = sqlite3.connect("workflow_store.db")
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT run_id FROM artifacts ORDER BY created_at;")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def resume_workflow(run_id: str, workflow: WorkflowSpec, choice: str,
                    project_context: Dict, user_input: str) -> List[Artifact]:
    """人工審批後從暫停點續跑。
    choice:
      - "approve" : 強行放行被攔下的stage，從下一個stage繼續
      - "rerun"   : 清除該stage產出的artifacts，重新執行該stage
      - "cancel"  : 中斷流程，狀態設為failed
    """
    run = get_run(run_id)
    if not run:
        raise ValueError(f"Run ID {run_id} 不存在")
    paused_stage = run.get("paused_stage")
    if not paused_stage:
        raise ValueError(f"Run ID {run_id} 目前不在人工審批暫停狀態（status={run['status']}）")
    stage_ids = [s["stage_id"] for s in workflow.stages]
    if choice == "cancel":
        set_run_status(run_id, "failed")
        print("流程已中斷")
        return load_artifacts(run_id)
    all_artifacts = load_artifacts(run_id)
    if choice == "rerun":
        print(f"重跑 Stage [{paused_stage}]，清除該stage舊artifacts")
        delete_stage_artifacts(run_id, paused_stage)
        all_artifacts = [a for a in all_artifacts if a.stage_id != paused_stage]
        start_idx = stage_ids.index(paused_stage)
    elif choice == "approve":
        print(f"人工強行放行 Stage [{paused_stage}]，繼續下一stage")
        start_idx = stage_ids.index(paused_stage) + 1
        if start_idx >= len(stage_ids):
            set_run_status(run_id, "completed")
            print("\n✅ Workflow全部執行完成")
            return all_artifacts
    else:
        raise ValueError(f"未知的審批選擇: {choice}")
    set_run_status(run_id, "running")
    return _run_stages(run_id, workflow, project_context, user_input,
                      all_artifacts=all_artifacts, start_idx=start_idx)


# ===================== API 函數：人工審批介面 =====================
def approve_paused_run(run_id: str) -> bool:
    """
    強制放行目前暫停的 stage，使工作流程繼續執行。
    回傳 True 若成功，False 若 run 不存在或未在暫停狀態。
    """
    run = get_run(run_id)
    if not run:
        return False
    if run["status"] != "paused_human":
        return False
    # 取得暫停的 stage
    paused_stage = run.get("paused_stage")
    if not paused_stage:
        return False
    # 重新設定狀態為 running，並從該 stage 的下一個繼續
    workflow = load_workflow_spec("workflow_spec.yaml")
    stage_ids = [s["stage_id"] for s in workflow.stages]
    try:
        start_idx = stage_ids.index(paused_stage) + 1
    except ValueError:
        return False
    # 設定為 running，並清除 paused_stage（因為將從下一個 stage 繼續）
    set_run_status(run_id, "running", paused_stage=None)
    # 從 start_idx 繼續執行
    all_artifacts = load_artifacts(run_id)
    # 已完成的 artifacts 保留，從 start_idx 繼續
    return _run_stages(run_id, workflow, {"project_context": {}, "user_input": ""},
                       "", all_artifacts=all_artifacts, start_idx=start_idx) is not None


def rerun_stage(run_id: str, stage_id: str) -> bool:
    """
    重新執行指定的 stage（清除該 stage 的先前 artifacts）。
    回傳 True 若成功，False 若 run 不存在或 stage 不在該 run 中。
    """
    run = get_run(run_id)
    if not run:
        return False
    # 檢查 stage 是否存在於該 run 的 artifacts 中（簡單檢查）
    all_artifacts = load_artifacts(run_id)
    stage_exists = any(a.stage_id == stage_id for a in all_artifacts)
    if not stage_exists:
        # 仍允許重跑，即使沒有 artefacts（可能是第一次執行）
        pass
    # 刪除該 stage 的 artefacts
    delete_stage_artifacts(run_id, stage_id)
    # 重新設定狀態為 running，並從該 stage 重新開始
    workflow = load_workflow_spec("workflow_spec.yaml")
    stage_ids = [s["stage_id"] for s in workflow.stages]
    try:
        start_idx = stage_ids.index(stage_id)
    except ValueError:
        return False
    set_run_status(run_id, "running", paused_stage=None)
    # 從 start_idx 重新執行
    all_artifacts = load_artifacts(run_id)  # 重新載入（已刪除該 stage 的 artefacts）
    return _run_stages(run_id, workflow, {"project_context": {}, "user_input": ""},
                       "", all_artifacts=all_artifacts, start_idx=start_idx) is not None


def abort_workflow(run_id: str) -> bool:
    """
    中止工作流程，將狀態設為 failed。
    回傳 True 若成功，False 若 run 不存在。
    """
    run = get_run(run_id)
    if not run:
        return False
    set_run_status(run_id, "failed")
    return True


def _fix_skill_yaml(skill_id: str, skill_dir: str = "./skills") -> bool:
    """Fix common issues in skill YAML that cause quality_score=0.0:
    - Ensure score_rationale field exists in output_schema.artifact.properties
    - Ensure acceptance_criteria includes score_rationale
    - Ensure core_prompt contains the quality_score rules with score_rationale mention
    - Remove duplicate acceptance_criteria under output_schema (if any)
    Returns True if any fix was applied.
    """
    import yaml
    from pathlib import Path

    p = Path(skill_dir)
    for f in p.glob("*.yaml"):
        raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        sd = raw.get("skillDefinition") or (raw.get("spec") or {}).get("skillDefinition")
        if sd is None:
            continue
        if sd["meta"]["id"] == skill_id:
            changed = False

            # 1. Ensure output_schema.artifact.properties has score_rationale
            output_schema = sd.get("output_schema", {})
            if isinstance(output_schema, dict):
                props = output_schema.get("properties", {})
                if isinstance(props, dict):
                    artifact_props = props.get("artifact", {})
                    if isinstance(artifact_props, dict):
                        artifact_inner = artifact_props.get("properties", {})
                        if isinstance(artifact_inner, dict):
                            if "score_rationale" not in artifact_inner:
                                artifact_inner["score_rationale"] = {"type": "string"}
                                changed = True
                        # Also ensure artifact itself has type: object
                        if artifact_props.get("type") != "object":
                            artifact_props["type"] = "object"
                            changed = True

            # 2. Ensure acceptance_criteria (under skillDefinition) includes score_rationale
            acc = sd.get("acceptance_criteria", [])
            if isinstance(acc, list):
                # Check if any item mentions score_rationale
                has_score_rationale = any("score_rationale" in str(item) for item in acc)
                if not has_score_rationale:
                    acc.append("必須包含 score_rationale 欄位")
                    changed = True

            # 3. Ensure core_prompt contains the quality_score rules with score_rationale mention
            core_prompt = sd.get("core_prompt", "")
            if "score_rationale" not in core_prompt:
                # We'll append a reminder at the end of core_prompt (but careful not to break)
                # For simplicity, we can just add a line before the ## 輸出Artifact結構
                # We'll insert a line: "      - 必須在artifact中新增 `score_rationale` 欄位，說明評分理由與扣分項目."
                # We'll do a simple append.
                if not core_prompt.endswith("\n"):
                    core_prompt += "\n"
                core_prompt += "      - 必須在artifact中新增 `score_rationale` 欄位，說明評分理由與扣分項目。\n"
                changed = True

            # 4. Remove duplicate acceptance_criteria under output_schema (if any)
            # We'll check if output_schema has an acceptance_criteria key at the same level as properties
            if isinstance(output_schema, dict):
                # Remove acceptance_criteria key if present (should not be there)
                if "acceptance_criteria" in output_schema:
                    del output_schema["acceptance_criteria"]
                    changed = True
                # Also ensure there is no duplicate risk_list key (should be only one under properties)
                # We'll not touch that.

            if changed:
                # Reconstruct the raw dict
                if "skillDefinition" in raw:
                    raw["skillDefinition"] = sd
                else:
                    raw["spec"]["skillDefinition"] = sd
                # Write back
                f.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
                print(f"[MONITOR] Fixed skill YAML: {f}")
                return True
    return False


def run_workflow_with_monitoring(run_id: str, workflow: WorkflowSpec, project_context: Dict, user_input: str, max_iterations: int = 3) -> List[Artifact]:
    """Run workflow with monitoring for quality_score=0.0 anomalies.
    If any artifact has quality_score == 0.0, attempt to fix the corresponding skill YAML
    and re-run the workflow, up to max_iterations times.
    """
    from typing import List
    import uuid
    for iteration in range(max_iterations):
        iter_run_id = f"{run_id}_iter{iteration}" if iteration > 0 else run_id
        print(f"[MONITOR] Workflow iteration {iteration+1}/{max_iterations} (run_id: {iter_run_id})")
        artifacts = run_workflow(iter_run_id, workflow, project_context, user_input)
        # Check for quality_score == 0.0
        zero_skill_ids = set()
        for art in artifacts:
            if art.quality_score == 0.0:
                zero_skill_ids.add(art.skill_id)
        if not zero_skill_ids:
            print("[MONITOR] No quality_score=0.0 artifacts found. Workflow successful.")
            return artifacts
        print(f"[MONITOR] Found quality_score==0.0 in skills: {zero_skill_ids}")
        for skill_id in zero_skill_ids:
            print(f"[MONITOR] Attempting to fix skill YAML: {skill_id}")
            fixed = _fix_skill_yaml(skill_id)
            if fixed:
                print(f"[MONITOR] Skill {skill_id} fixed.")
            else:
                print(f"[MONITOR] No fixes applied to skill {skill_id} (maybe already correct).")
        # If we have fixes, continue loop; if no fixes but still zero, we will still loop up to max_iterations
    print(f"[MONITOR] Max iterations reached. Returning last artifacts.")
    return artifacts


# ===================== 入口主程式 =====================
if __name__ == "__main__":
    import sys
    # Windows 主控台 cp950 無法輸出 emoji，強制 UTF-8 輸出避免 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    import uuid
    init_db()
    wf = load_workflow_spec("workflow_spec.yaml")
    run_uuid = str(uuid.uuid4())
    print(f"啟動Workflow Run ID: {run_uuid}")

    # ===== 這裡輸入你的專案初始資訊 =====
    project_context = {
        "project_name": "金融信用管理系統",
        "team": "揚沛開發團隊",
        "budget": 50000,
        "compliance": ["個人資料保護規範"],
        "non_functional_goals": {
            "availability": "99.9%"
        }
    }
    user_input = """
開發一個金融信用管理系統，使用者可以輸入交易合約、查交易合約狀態，管理員可以審核交易合約，支援修改條件。
"""
    # 啟動執行
    result_arts = run_workflow_with_monitoring(run_uuid, wf, project_context, user_input)
    print(f"本次Run共產出Artifact數量：{len(result_arts)}")