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


# ===================== Gate 自訂例外（供Streamlit攔截） =====================
class GatePause(Exception):
    """Gate不通過且需人工審批時拋出，攜帶暫停點資訊供UI續跑"""
    def __init__(self, stage_id: str, skill_id: str, message: str):
        self.stage_id = stage_id
        self.skill_id = skill_id
        self.message = message
        super().__init__(f"GATE_PAUSE|stage={stage_id}|skill={skill_id}|msg={message}")


# ===================== DB初始化 =====================
def _migrate_db(cur):
    """舊版DB補欄位：workflow_runs.paused_stage（人工審批暫停點）"""
    cols = [r[1] for r in cur.execute("PRAGMA table_info(workflow_runs)").fetchall()]
    if "paused_stage" not in cols:
        cur.execute("ALTER TABLE workflow_runs ADD COLUMN paused_stage TEXT")


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
            return SkillDef(
                meta=sd["meta"],
                input_schema=sd["input_schema"],
                core_prompt=sd["core_prompt"],
                acceptance_criteria=sd["acceptance_criteria"],
                output_schema=sd["output_schema"],
                error_handler=sd["error_handler"]
            )
    raise FileNotFoundError(f"Skill id {skill_id} not found in {skill_dir}")


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


# ===================== Gate 閘門檢查 =====================
def gate_check(artifact: Artifact, cross_artifacts: List[Artifact], gate_config: Dict) -> tuple[bool, str]:
    """回傳 (pass:bool, message)"""
    msg_list = []
    pass_flag = True
    if artifact.quality_score < gate_config["quality_score_min"]:
        pass_flag = False
        msg_list.append(f"主Skill quality_score {artifact.quality_score} < 門檻 {gate_config['quality_score_min']}")

    for ca in cross_artifacts:
        if not isinstance(ca.artifact, dict):
            # 容錯：artifact 結構異常時，不視為阻斷，避免流程卡死
            continue
        if ca.skill_id == "skill_se_sec_compliance":
            vulns = ca.artifact.get("blocking_vulnerabilities", [])
            if len(vulns) > 0 and gate_config.get("block_if_critical_vuln"):
                pass_flag = False
                msg_list.append(f"安全審計發現阻斷型漏洞：{vulns}")
        if ca.skill_id == "skill_se_cost_control":
            # Check the risk_list for Critical or High risks with no mitigation
            critical_high_risks_no_mitigation = [
                r for r in ca.risk_list
                if r.get("level") in ["Critical", "High"]
                and not r.get("mitigation", "").strip()
            ]
            if len(critical_high_risks_no_mitigation) > 0 and gate_config.get("block_if_critical_vuln"):
                pass_flag = False
                msg_list.append(f"成本控制發現阻斷型風險：{critical_high_risks_no_mitigation}")
    return pass_flag, "\n".join(msg_list)


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
        if skill_id in code_generating_skills:
            print(f" -> 偵測到程式碼生成階段，先執行 my-code-standard 作為前置檢查...")
            my_cs_skill = load_skill("my-code-standard")
            # 為my-code-standard準備輸入 - 它需要專案內容和使用者輸入
            my_cs_art = execute_skill(my_cs_skill, project_context, all_artifacts, user_input)
            # 不將my-code-standard作為獨立artefact保存，只作為前置檢查
            print(f"   my-code-standard 前置檢查完成，quality_score: {my_cs_art.quality_score}")

            # 如果my-code-standard品質分數低於門檻，則拋出GatePause
            if my_cs_art.quality_score < workflow.gate["quality_score_min"]:
                gate_pass, gate_msg = gate_check(my_cs_art, [], workflow.gate)
                if not gate_pass and workflow.gate.get("human_approval"):
                    set_run_status(run_id, "paused_human", paused_stage=stage_id)
                    print("\n===== 流程暫停（my-code-standard 前置檢查未通過品質門檻），等待人工審批 =====")
                    print("選項: [A]強行放行 [R]修正後重跑本stage [X]中斷流程")
                    raise GatePause(stage_id, skill_id, f"my-code-standard 前置檢查未通過: {gate_msg}")

        skill = load_skill(skill_id)
        dep_stage_ids = stage.get("depends_on", [])
        deps_arts = [a for a in all_artifacts if a.stage_id in dep_stage_ids]

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

        gate_pass, gate_msg = gate_check(main_art, cross_arts, workflow.gate)
        print(f"\nGate檢查結果: {gate_pass}, 訊息: {gate_msg}")
        if not gate_pass and workflow.gate.get("human_approval"):
            set_run_status(run_id, "paused_human", paused_stage=stage_id)
            print("\n===== 流程暫停，等待人工審批 =====")
            print("選項: [A]強行放行 [R]修正後重跑本stage [X]中斷流程")
            raise GatePause(stage_id, skill_id, gate_msg)
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



# import os
# import re
# import yaml
# import json
# import sqlite3
# import requests
# from dotenv import load_dotenv
# from pydantic import BaseModel, Field
# from typing import Dict, Any, List, Optional
# from pathlib import Path

# # ===================== 載入環境變數 =====================
# load_dotenv()
# # ===================== Free Claude Code (FCC) Proxy 設定 =====================
# # FCC（free-claude-code）以 fcc-server 啟動後，預設監聽 http://0.0.0.0:8082
# # （可用 HOST / PORT 環境變數覆蓋，請和 FCC 的實際 port 一致）。
# #
# # 重要：你這套 FCC 只暴露 Anthropic 相容端點 POST /v1/messages
# #       （/v1/responses 與 /v1/chat/completions 皆 404），
# #       所以本程式直接用 HTTP POST /v1/messages（Anthropic Messages 協定）。
# #       若 FCC 有開 auth（PROXY_AUTH_ENABLED=true），Bearer token 為 ANTHROPIC_AUTH_TOKEN（預設 freecc）。
# #
# # 使用前請先啟動 FCC：  fcc-server
# # model 請填 FCC /v1/models 回傳的 Claude model id；FCC 會把該請求路由到 Admin UI
# # 設定的上游 provider（請在 http://127.0.0.1:8082/admin 確認上游模型可用）。
# FCC_BASE_URL = os.getenv("FCC_BASE_URL", "http://127.0.0.1:8082")  # 根路徑（不含 /v1）
# FCC_API_KEY = os.getenv("FCC_API_KEY", "freecc")  # 認證 token（ANTHROPIC_AUTH_TOKEN）
# # FCC 只會把這個 model 視為「要路由的目標」，實際上游模型由 FCC .env 的 MODEL 決定。
# # 此處用 FCC /v1/models 所公佈的 Claude id，僅供比對/顯示。
# FCC_MODEL = os.getenv("FCC_MODEL", "claude-sonnet-4-20250514")
# # ---- 模型 Failover Chain ----
# # 經實測，此版 FCC「沒有」內建 failover（FAILOVER_MODELS 會被忽略），
# # 但 FCC 接受 client 直接以「provider_type/model/name」完整格式指定上游模型
# # （例：nvidia_nim/minimaxai/minimax-m3 會直接路由到該模型，不被 MODEL 映射覆蓋）。
# # 因此 failover 由本程式實作：主模型失敗（HTTP 錯誤 / provider 錯誤 / 逾時 / 空回應）
# # 時，自動依序改用下列備援模型。
# # NVIDIA NIM 實測結果（2026-09-04）：
# #   - nvidia/nemotron-3-super-120b-a12b : 穩定可用（約 1 秒）
# #   - minimaxai/minimax-m3              : 可用但較慢（約 24 秒）
# #   - 其餘（deepseek-v4-pro、mistral-large、ultra-550b 等）皆不穩定或 404/逾時
# FCC_FAILOVER_MODELS = [
#     m.strip() for m in os.getenv(
#         "FCC_FAILOVER_MODELS",
#         "nvidia_nim/minimaxai/minimax-m3",
#     ).split(",") if m.strip()
# ]
# # 每個模型的重試次數（FCC 對上游偶發 transport error，重試通常即可成功）
# FCC_RETRIES = int(os.getenv("FCC_RETRIES", "2"))
# # 單次LLM輸出的max_tokens上限；若JSON被截斷會自動以兩倍上限重試一次
# FCC_MAX_TOKENS = int(os.getenv("FCC_MAX_TOKENS", "8192"))
# DB_PATH = os.getenv("DB_PATH", "./db/se_agent.db")
# QUALITY_THRESHOLD = float(os.getenv("QUALITY_THRESHOLD", 70))


# def _parse_anthropic_response(body: str) -> str:
#     """解析 FCC 回應：支援 SSE event 流與標準 Anthropic JSON 兩種格式，回傳純文字。"""
#     stripped = body.lstrip()
#     # FCC 回 SSE 流（event: ... \n data: {...}）
#     if stripped.startswith("event:"):
#         parts: List[str] = []
#         for line in body.splitlines():
#             if not line.startswith("data: "):
#                 continue
#             data = json.loads(line[6:])
#             t = data.get("type")
#             delta = data.get("delta") or {}
#             txt = delta.get("text")
#             if t == "content_block_delta" and txt:
#                 parts.append(txt)
#         return "".join(parts).strip()

#     # 標準 Anthropic JSON
#     obj = json.loads(body)
#     blocks = obj.get("content", [])
#     texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
#     return "".join(texts).strip()


# def call_anthropic_messages(system_prompt: str, user_msg: str, max_tokens: Optional[int] = None) -> str:
#     """呼叫 FCC 的 Anthropic /v1/messages 端點，回傳回覆文字。

#     內建模型 failover：依 FCC_MODEL -> FCC_FAILOVER_MODELS 順序嘗試，
#     每個模型重試 FCC_RETRIES 次；全部失敗才 raise RuntimeError。
#     判定失敗的條件：HTTP >= 400、連線/逾時例外、上游 provider 錯誤
#     （「Provider API request failed」）、解析失敗或空回應。
#     """
#     if max_tokens is None:
#         max_tokens = FCC_MAX_TOKENS
#     url = f"{FCC_BASE_URL.rstrip('/')}/v1/messages"
#     headers = {
#         "Authorization": f"Bearer {FCC_API_KEY}",
#         "Content-Type": "application/json",
#     }
#     model_chain = [FCC_MODEL] + [m for m in FCC_FAILOVER_MODELS if m != FCC_MODEL]

#     last_err: str = "unknown"
#     for model in model_chain:
#         for attempt in range(1, FCC_RETRIES + 1):
#             payload = {
#                 "model": model,
#                 "max_tokens": max_tokens,
#                 "system": system_prompt,
#                 "messages": [{"role": "user", "content": user_msg}],
#             }
#             try:
#                 resp = requests.post(url, headers=headers, json=payload, timeout=(10, 600))
#             except requests.RequestException as exc:
#                 last_err = f"{model} #{attempt}: {type(exc).__name__}: {exc}"
#                 print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
#                 continue

#             if resp.status_code >= 400:
#                 last_err = f"{model} #{attempt}: HTTP {resp.status_code} {resp.text[:200]}"
#                 print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
#                 continue

#             if "Provider API request failed" in resp.text:
#                 last_err = f"{model} #{attempt}: 上游 provider 錯誤"
#                 print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
#                 continue

#             try:
#                 text = _parse_anthropic_response(resp.text)
#             except (json.JSONDecodeError, ValueError) as exc:
#                 last_err = f"{model} #{attempt}: 回應解析失敗 {type(exc).__name__}: {exc}"
#                 print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
#                 continue

#             if not text:
#                 last_err = f"{model} #{attempt}: 空回應"
#                 print(f"[FCC] 呼叫失敗，將重試/換模型 -> {last_err}")
#                 continue

#             if model != FCC_MODEL:
#                 print(f"[FCC] 已自動切換至備援模型: {model}")
#             return text

#     raise RuntimeError(f"FCC 所有模型（{model_chain}）皆失敗，最後錯誤: {last_err}")

# # ===================== Pydantic 資料模型 =====================
# class SkillDef(BaseModel):
#     meta: Dict[str, Any]
#     input_schema: Dict[str, Any]
#     core_prompt: str
#     acceptance_criteria: List[str]
#     output_schema: Dict[str, Any]
#     error_handler: Dict[str, Any]

# class WorkflowSpec(BaseModel):
#     workflow_id: str
#     name: str
#     description: str
#     version: str
#     cross_cutting_skills: List[Dict[str,str]]
#     gate: Dict[str, Any]
#     stages: List[Dict[str, Any]]

# class Artifact(BaseModel):
#     skill_id: str
#     stage_id: Optional[str] = None
#     artifact: Dict[str, Any]
#     unresolved_questions: List[Any]
#     risk_list: List[Any]
#     quality_score: float
#     raw_llm_output: str

# # ===================== DB初始化 =====================
# def _migrate_db(cur):
#     """舊版DB補欄位：workflow_runs.paused_stage（人工審批暫停點）"""
#     cols = [r[1] for r in cur.execute("PRAGMA table_info(workflow_runs)").fetchall()]
#     if "paused_stage" not in cols:
#         cur.execute("ALTER TABLE workflow_runs ADD COLUMN paused_stage TEXT")

# def init_db():
#     db_dir = Path(DB_PATH).parent
#     db_dir.mkdir(exist_ok=True)
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS workflow_runs (
#         run_id TEXT PRIMARY KEY,
#         workflow_id TEXT,
#         status TEXT, -- running / paused_human / completed / failed
#         paused_stage TEXT,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     """)
#     _migrate_db(cur)
#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS artifacts (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         run_id TEXT,
#         skill_id TEXT,
#         stage_id TEXT,
#         payload TEXT,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
#     )
#     """)
#     conn.commit()
#     conn.close()

# def save_artifact(run_id: str, stage_id: str, skill_id: str, artifact: Artifact):
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     payload = artifact.model_dump_json()
#     cur.execute(
#         "INSERT INTO artifacts(run_id, skill_id, stage_id, payload) VALUES (?,?,?,?)",
#         (run_id, skill_id, stage_id, payload)
#     )
#     conn.commit()
#     conn.close()

# def load_artifacts(run_id: str) -> List[Artifact]:
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     rows = cur.execute("SELECT payload FROM artifacts WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
#     conn.close()
#     arts = []
#     for r in rows:
#         data = json.loads(r[0])
#         arts.append(Artifact(**data))
#     return arts

# def delete_stage_artifacts(run_id: str, stage_id: str):
#     """刪除某run某stage的所有artifact（人工審批選擇重跑時用）"""
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     cur.execute("DELETE FROM artifacts WHERE run_id=? AND stage_id=?", (run_id, stage_id))
#     conn.commit()
#     conn.close()

# def set_run_status(run_id: str, status: str, paused_stage: Optional[str] = None):
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     if paused_stage is not None:
#         cur.execute("UPDATE workflow_runs SET status=?, paused_stage=? WHERE run_id=?", (status, paused_stage, run_id))
#     else:
#         cur.execute("UPDATE workflow_runs SET status=? WHERE run_id=?", (status, run_id))
#     conn.commit()
#     conn.close()

# def get_run(run_id: str) -> Optional[Dict]:
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     row = conn.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
#     conn.close()
#     return dict(row) if row else None

# # ===================== Skill YAML 載入器 =====================
# def load_skill(skill_id: str, skill_dir: str = "./skills") -> SkillDef:
#     """讀取skill yaml，根據meta.id匹配（支援頂層 skillDefinition 或 Harness spec.skillDefinition 結構）"""
#     p = Path(skill_dir)
#     for f in p.glob("*.yaml"):
#         raw = yaml.safe_load(f.read_text(encoding="utf-8"))
#         sd = raw.get("skillDefinition") or (raw.get("spec") or {}).get("skillDefinition")
#         if sd is None:
#             continue
#         if sd["meta"]["id"] == skill_id:
#             return SkillDef(
#                 meta=sd["meta"],
#                 input_schema=sd["input_schema"],
#                 core_prompt=sd["core_prompt"],
#                 acceptance_criteria=sd["acceptance_criteria"],
#                 output_schema=sd["output_schema"],
#                 error_handler=sd["error_handler"]
#             )
#     raise FileNotFoundError(f"Skill id {skill_id} not found in {skill_dir}")

# def load_workflow_spec(path: str = "workflow_spec.yaml") -> WorkflowSpec:
#     raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
#     return WorkflowSpec(**raw)

# # ===================== LLM JSON 解析與修復 =====================
# def _strip_code_fence(text: str) -> str:
#     """去掉 markdown code fence 與前後雜訊，取出 JSON 主體片段"""
#     # Handle markdown code fences by extracting content between fences
#     # Look for all code fence blocks
#     code_fence_pattern = r'```[a-zA-Z]*\s*(.*?)\s*```'
#     matches = list(re.finditer(code_fence_pattern, text, re.DOTALL))

#     if matches:
#         # If we found code fence blocks, try to extract JSON from them
#         # Prefer blocks that look like they contain JSON (start with { or [)
#         json_candidates = []
#         for match in matches:
#             content = match.group(1)
#             # Check if content looks like it contains JSON
#             stripped_content = content.strip()
#             if stripped_content.startswith('{') or stripped_content.startswith('['):
#                 json_candidates.append(content)

#         # If we found JSON-like candidates, use the last one (most likely to be the intended output)
#         if json_candidates:
#             # Use the last JSON-like candidate
#             selected_content = json_candidates[-1]
#         else:
#             # If no JSON-like content found, use the last code fence block content
#             selected_content = matches[-1].group(1)

#         # Now find JSON start in the selected content
#         t = selected_content
#     else:
#         # No code fences found, work with original text
#         t = text.strip()

#     # Find the first { or [ to locate JSON start
#     start_curly = t.find("{")
#     start_bracket = t.find("[")

#     # Determine which comes first (or if only one exists)
#     start_pos = -1
#     if start_curly != -1 and start_bracket != -1:
#         start_pos = min(start_curly, start_bracket)
#     elif start_curly != -1:
#         start_pos = start_curly
#     elif start_bracket != -1:
#         start_pos = start_bracket

#     if start_pos == -1:
#         return t  # No JSON structure found, return as-is

#     # From the start position, try to find valid JSON by balancing braces/brackets
#     return _extract_json_from_text(t[start_pos:])


# def _extract_json_from_text(text: str) -> str:
#     """從文本中提取有效的JSON片段，處理可能的截斷情況"""
#     if not text:
#         return text

#     # Try to find balanced JSON object or array
#     stack = []
#     in_string = False
#     escape_next = False

#     for i, ch in enumerate(text):
#         if escape_next:
#             escape_next = False
#             continue

#         if ch == '\\':
#             escape_next = True
#             continue

#         if ch == '"' and not escape_next:
#             in_string = not in_string
#             continue

#         if in_string:
#             continue

#         if ch in '{[':
#             stack.append(ch)
#         elif ch in '}]':
#             if not stack:
#                 # Unmatched closing brace/bracket, return what we have so far
#                 return text[:i]
#             opening = stack.pop()
#             if (opening == '{' and ch != '}') or (opening == '[' and ch != ']'):
#                 # Mismatched brackets
#                 return text[:i]

#             # If stack is empty, we've found a complete JSON object/array
#             if not stack:
#                 return text[:i+1]

#     # If we parsed through the entire text and still have unclosed structures,
#     # return what we have (the calling function will attempt to fix it)
#     return text

# def _close_open_json(s: str) -> str:
#     """掃描未閉合的字串與括號，補上結尾使其成為合法JSON（截斷修復用）"""
#     stack: List[str] = []
#     in_str = False
#     esc = False
#     for ch in s:
#         if in_str:
#             if esc:
#                 esc = False
#             elif ch == "\\":
#                 esc = True
#             elif ch == '"':
#                 in_str = False
#         else:
#             if ch == '"':
#                 in_str = True
#             elif ch in "{[":
#                 stack.append(ch)
#             elif ch in "}]":
#                 if stack:
#                     stack.pop()
#     suffix = '"' if in_str else ""
#     suffix += "".join("}" if c == "{" else "]" for c in reversed(stack))
#     return s + suffix


# def _fix_common_json_issues(text: str) -> str:
#     """修復常見的JSON問題，如尾隨逗號、單引號、註解等"""
#     # 移除單行註釋 (// 註釋)，但要小心不要移除URL中的http://
#     lines = text.split('\n')
#     cleaned_lines = []
#     for line in lines:
#         # 找到第一個不在字串內的//
#         in_string = False
#         escape_next = False
#         for i, ch in enumerate(line):
#             if escape_next:
#                 escape_next = False
#                 continue
#             if ch == '\\':
#                 escape_next = True
#                 continue
#             if ch == '"' and not escape_next:
#                 in_string = not in_string
#                 continue
#             if not in_string and i + 1 < len(line) and line[i:i+2] == '//':
#                 line = line[:i]
#                 break
#         cleaned_lines.append(line)
#     text = '\n'.join(cleaned_lines)

#     # 移除多行註釋 /* ... */ (簡單版本，不處理嵌套)
#     while '/*' in text and '*/' in text:
#         start = text.find('/*')
#         end = text.find('*/', start + 2)
#         if end != -1:
#             text = text[:start] + text[end+2:]
#         else:
#             break

#     # 替換單引號為雙引號（但要小心不要替換縮寫如don't）
#     # 這是一個簡單的方法，可能不完美但能處理大多數情況
#     # 更好的方法是解析JSON並重新序列化，但這需要先有部分有效的JSON

#     # 移除尾隨逗號（在}或]之前）
#     # 這個正則會匹配 , 後面跟著任意空白和 } 或 ] 的情況
#     text = re.sub(r',(\s*[}\]])', r'\1', text)

#     return text

# def parse_llm_json(text: str) -> Dict[str, Any]:
#     """解析LLM回傳的JSON，具備容錯：
#     1. 去code fence、取第一個 { 之後的內容
#     2. 清除常見JSON問題（註釋、尾隨逗號等）
#     3. 直接json.loads
#     4. 失敗則視為截斷，補閉合括號再試
#     5. 仍失敗則從尾端逐個邊界往回剪，剪一段補閉合試一次（修復殘缺的key/value）
#     """
#     # 步驟1: 去code fence並提取JSON主體
#     body = _strip_code_fence(text)

#     # 步驟2: 清除常見JSON問題
#     cleaned_body = _fix_common_json_issues(body)

#     candidates: List[str] = [cleaned_body]

#     # 候選2：直接補閉合
#     candidates.append(_close_open_json(cleaned_body))

#     # 候選3+：從尾端結構邊界往回剪，每段補閉合（處理截斷在key/value中間的殘尾）
#     cut_points = [i for i, ch in enumerate(cleaned_body) if ch in ",}\""]
#     for cp in reversed(cut_points[-60:]):
#         frag = cleaned_body[:cp + 1] if cleaned_body[cp] in ",}" else cleaned_body[:cp]
#         candidates.append(_close_open_json(frag))

#     last_err: Exception = ValueError("empty content")
#     for cand in candidates:
#         if not cand.strip():
#             continue
#         try:
#             return json.loads(cand)
#         except json.JSONDecodeError as exc:
#             last_err = exc
#     raise ValueError(f"LLM JSON解析失敗（含截斷修復嘗試）：{last_err}\n原始輸出前200字：{text[:200]!r}")

# # ===================== LLM Skill 執行核心 =====================
# def execute_skill(skill: SkillDef, project_context: Dict, previous_artifacts: List[Artifact], user_input: str) -> Artifact:
#     """呼叫LLM執行單一支Skill，強制輸出JSON（含截斷自動重試）"""
#     prev_payload = [a.model_dump() for a in previous_artifacts]
#     system_prompt = f"""
# {skill.core_prompt}

# 【驗收準則】
# {yaml.dump(skill.acceptance_criteria)}

# 【強制輸出規則】
# 你必須只回傳嚴格JSON，不要前言、不要解釋、不要markdown code fence。
# 輸出必須完全符合output_schema結構：
# {json.dumps(skill.output_schema, indent=2)}
# """
#     user_msg = json.dumps({
#         "project_context": project_context,
#         "user_input": user_input,
#         "previous_artifacts": prev_payload
#     }, ensure_ascii=False, indent=2)

#     raw_text = call_anthropic_messages(system_prompt, user_msg)
#     try:
#         parsed = parse_llm_json(raw_text)
#     except ValueError as e:
#         # 很可能是輸出被max_tokens截斷 -> 放寬上限兩倍，並要求精簡後重試一次
#         print(f"[execute_skill] JSON解析失敗（疑似截斷或格式錯誤），以max_tokens={FCC_MAX_TOKENS*2}重試一次: {str(e)[:100]}...")
#         system_prompt_retry = system_prompt + "\n注意：輸出空間有限，請精簡內容（每個清單最多5項、描述一句話），確保JSON完整閉合。"
#         raw_text = call_anthropic_messages(system_prompt_retry, user_msg, max_tokens=FCC_MAX_TOKENS * 2)
#         try:
#             parsed = parse_llm_json(raw_text)
#         except ValueError as retry_e:
#             # 如果重試仍然失敗，記錄詳細錯誤並使用預設值
#             print(f"[execute_skill] 重試後仍然失敗: {str(retry_e)[:200]}")
#             print(f"[execute_skill] 原始LLM輸出前500字符: {raw_text[:500]}")
#             # 嘗試最後一次純粹的提取嘗試 - 只尋找數字形式的quality_score
#             parsed = {"artifact": {}, "unresolved_questions": [], "risk_list": [], "quality_score": 0}

#             # 嘗試從原始文本中提取quality_score
#             quality_match = re.search(r'"quality_score"\s*:\s*(\d+(?:\.\d+)?)', raw_text)
#             if quality_match:
#                 try:
#                     parsed["quality_score"] = float(quality_match.group(1))
#                     print(f"[execute_skill] 從原始文本中提取到quality_score: {parsed['quality_score']}")
#                 except ValueError:
#                     pass

#     # 確保quality_score是有效的數字且在範圍內
#     quality_score = parsed.get("quality_score", 0)
#     try:
#         quality_score = float(quality_score)
#         # 確保在0-100範圍內
#         if quality_score < 0:
#             quality_score = 0
#         elif quality_score > 100:
#             quality_score = 100
#     except (ValueError, TypeError):
#         quality_score = 0
#         print(f"[execute_skill] quality_score無效，使用預設值0: {parsed.get('quality_score')}")

#     art = Artifact(
#         skill_id=skill.meta["id"],
#         artifact=parsed.get("artifact", {}),
#         unresolved_questions=parsed.get("unresolved_questions", []),
#         risk_list=parsed.get("risk_list", []),
#         quality_score=quality_score,
#         raw_llm_output=raw_text
#     )
#     return art

# # ===================== Gate 閘門檢查 =====================
# def gate_check(artifact: Artifact, cross_artifacts: List[Artifact], gate_config: Dict) -> tuple[bool, str]:
#     """回傳 (pass:bool, message)"""
#     msg_list = []
#     pass_flag = True

#     if artifact.quality_score < gate_config["quality_score_min"]:
#         pass_flag = False
#         msg_list.append(f"主Skill quality_score {artifact.quality_score} < 門檻 {gate_config['quality_score_min']}")

#     # 檢查安全合規橫切skill的 blocking_vulnerabilities
#     for ca in cross_artifacts:
#         if ca.skill_id == "skill-se-sec-compliance":
#             vulns = ca.artifact.get("blocking_vulnerabilities", [])
#             if len(vulns) > 0 and gate_config.get("block_if_critical_vuln"):
#                 pass_flag = False
#                 msg_list.append(f"安全審計發現阻斷型漏洞：{vulns}")
#     return pass_flag, "\n".join(msg_list)

# # ===================== Workflow 主執行器 =====================
# class GatePause(Exception):
#     """Gate不通過且需人工審批時拋出，攜帶暫停點資訊供UI續跑"""
#     def __init__(self, stage_id: str, skill_id: str, message: str):
#         self.stage_id = stage_id
#         self.skill_id = skill_id
#         self.message = message
#         super().__init__(f"GATE_PAUSE|stage={stage_id}|skill={skill_id}|msg={message}")

# def _set_run_status(run_id: str, status: str, paused_stage: Optional[str] = None):
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     if paused_stage is not None:
#         cur.execute("UPDATE workflow_runs SET status=?, paused_stage=? WHERE run_id=?", (status, paused_stage, run_id))
#     else:
#         cur.execute("UPDATE workflow_runs SET status=? WHERE run_id=?", (status, run_id))
#     conn.commit()
#     conn.close()

# def _get_run(run_id: str) -> Optional[Dict]:
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     row = conn.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
#     conn.close()
#     return dict(row) if row else None

# def _run_stages(run_id: str, workflow: WorkflowSpec, project_context: Dict, user_input: str,
#                 all_artifacts: List[Artifact], start_idx: int = 0) -> List[Artifact]:
#     """從指定stage索引開始執行；Gate不通過且需人工審批時拋出GatePause"""
#     for stage in workflow.stages[start_idx:]:
#         stage_id = stage["stage_id"]
#         skill_id = stage["skill_id"]
#         print(f"\n===== 執行 Stage [{stage_id}] Skill:{skill_id} =====")
#         skill = load_skill(skill_id)

#         # 收集此stage依賴的前置artifact
#         dep_stage_ids = stage.get("depends_on", [])
#         deps_arts = [a for a in all_artifacts if a.stage_id in dep_stage_ids]

#         # 執行主Skill
#         main_art = execute_skill(skill, project_context, deps_arts, user_input)
#         main_art.stage_id = stage_id
#         all_artifacts.append(main_art)
#         save_artifact(run_id, stage_id, skill_id, main_art)
#         print(f"主Skill quality_score: {main_art.quality_score}")

#         # 並行執行 Cross-cutting 橫切Skill
#         cross_arts: List[Artifact] = []
#         for cross_def in workflow.cross_cutting_skills:
#             cross_skill_id = cross_def["skill_id"]
#             print(f" -> 執行橫切審計: {cross_skill_id}")
#             cross_skill = load_skill(cross_skill_id)
#             cross_art = execute_skill(cross_skill, project_context, all_artifacts, user_input)
#             cross_art.stage_id = stage_id
#             cross_arts.append(cross_art)
#             all_artifacts.append(cross_art)
#             save_artifact(run_id, stage_id, cross_skill_id, cross_art)

#         # Gate檢查
#         gate_pass, gate_msg = gate_check(main_art, cross_arts, workflow.gate)
#         print(f"\nGate檢查結果: {gate_pass}, 訊息: {gate_msg}")
#         if not gate_pass and workflow.gate.get("human_approval"):
#             # 暫停，記錄暫停點，等待人工審批（由UI決定放行/重跑/中斷）
#             _set_run_status(run_id, "paused_human", paused_stage=stage_id)
#             print("\n===== 流程暫停，等待人工審批 =====")
#             print("選項: [A]強行放行 [R]修正後重跑本stage [X]中斷流程")
#             raise GatePause(stage_id, skill_id, gate_msg)

#     # 全部Stage跑完
#     _set_run_status(run_id, "completed")
#     print("\n✅ Workflow全部執行完成")
#     return all_artifacts

# def run_workflow(run_id: str, workflow: WorkflowSpec, project_context: Dict, user_input: str) -> List[Artifact]:
#     """全新執行一次workflow。Gate暫停時拋出GatePause（可之後以resume_workflow續跑）"""
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     cur.execute("INSERT INTO workflow_runs(run_id, workflow_id, status, paused_stage) VALUES (?,?,?,?)",
#                 (run_id, workflow.workflow_id, "running", None))
#     conn.commit()
#     conn.close()
#     return _run_stages(run_id, workflow, project_context, user_input, all_artifacts=[], start_idx=0)

# def resume_workflow(run_id: str, workflow: WorkflowSpec, choice: str,
#                     project_context: Dict, user_input: str) -> List[Artifact]:
#     """人工審批後從暫停點續跑。

#     choice:
#       - "approve" : 強行放行被攔下的stage，從下一個stage繼續
#       - "rerun"   : 清除該stage產出的artifacts，重新執行該stage
#       - "cancel"  : 中斷流程，狀態設為failed
#     """
#     run = _get_run(run_id)
#     if not run:
#         raise ValueError(f"Run ID {run_id} 不存在")
#     paused_stage = run.get("paused_stage")
#     if not paused_stage:
#         raise ValueError(f"Run ID {run_id} 目前不在人工審批暫停狀態（status={run['status']}）")

#     stage_ids = [s["stage_id"] for s in workflow.stages]

#     if choice == "cancel":
#         _set_run_status(run_id, "failed")
#         print("流程已中斷")
#         return load_artifacts(run_id)

#     all_artifacts = load_artifacts(run_id)

#     if choice == "rerun":
#         print(f"重跑 Stage [{paused_stage}]，清除該stage舊artifacts")
#         delete_stage_artifacts(run_id, paused_stage)
#         all_artifacts = [a for a in all_artifacts if a.stage_id != paused_stage]
#         start_idx = stage_ids.index(paused_stage)
#     elif choice == "approve":
#         print(f"人工強行放行 Stage [{paused_stage}]，繼續下一stage")
#         start_idx = stage_ids.index(paused_stage) + 1
#         if start_idx >= len(stage_ids):
#             _set_run_status(run_id, "completed")
#             print("\n✅ Workflow全部執行完成")
#             return all_artifacts
#     else:
#         raise ValueError(f"未知的審批選擇: {choice}")

#     _set_run_status(run_id, "running")
#     return _run_stages(run_id, workflow, project_context, user_input,
#                        all_artifacts=all_artifacts, start_idx=start_idx)

# # ===================== 入口主程式 =====================
# if __name__ == "__main__":
#     import uuid
#     init_db()
#     wf = load_workflow_spec("workflow_spec.yaml")
#     run_uuid = str(uuid.uuid4())
#     print(f"啟動Workflow Run ID: {run_uuid}")

#     # ===== 這裡輸入你的專案初始資訊 =====
#     project_context = {
#         "project_name": "金融信用管理系統",
#         "team": "揚沛開發團隊",
#         "budget": 50000,
#         "compliance": ["個人資料保護規範"],
#         "non_functional_goals": {
#             "availability": "99.9%"
#         }
#     }
#     user_input = """
# 開發一個金融信用管理系統，使用者可以輸入交易合約、查交易合約狀態，管理員可以審核交易合約，支援修改條件。
# """
#     # 啟動執行
#     result_arts = run_workflow(run_uuid, wf, project_context, user_input)
#     print(f"本次Run共產出Artifact數量：{len(result_arts)}")
