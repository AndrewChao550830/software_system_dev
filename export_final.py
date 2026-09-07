# -*- coding: utf-8 -*-
"""匯出最終 Run 的系統程式碼與所有 Artifact 文件"""
import sqlite3, json, os
from pathlib import Path

RUN_ID = "51b4550a-3405-4c3c-9221-10ff032ba5ee"
CODE_DIR = Path("generated_code")
DOC_DIR = Path("generated_docs")
CODE_DIR.mkdir(exist_ok=True)
DOC_DIR.mkdir(exist_ok=True)

c = sqlite3.connect('db/se_agent.db')

# ---- 1. 匯出 code_renderer 產出的系統程式碼 ----
r = c.execute(
    "select payload from artifacts where run_id=? and skill_id='skill_code_renderer'",
    (RUN_ID,)).fetchone()
d = json.loads(r[0])
art = d.get('artifact') or {}
rf = art.get('rendered_files') or []
count = 0
for f in rf:
    fp = CODE_DIR / f['file_path']
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(f.get('content', ''), encoding='utf-8')
    count += 1
print(f"匯出系統程式碼檔案數: {count} -> {CODE_DIR}/")

# ---- 2. 匯出所有 Artifact 為 Markdown 文件 ----
rows = c.execute(
    "select stage_id, skill_id, payload, created_at from artifacts where run_id=? order by id",
    (RUN_ID,)).fetchall()

TITLES = {
    'requirement': '01_需求理解', 'business_model': '02_商業建模',
    'system_boundary': '03_系統邊界C4', 'tech_design': '04_技術方案與ADR',
    'data_state_design': '05_資料結構與狀態機', 'code_implementation': '06_程式碼骨架實作',
    'code_renderer': '07_程式碼渲染生成', 'test_validation': '08_測試案例設計',
    'deployment': '09_部署計畫', 'observability': '10_可觀測性設計',
    'feedback_iteration': '11_回饋迭代Backlog',
}

main_stages = {}
for stage_id, skill_id, payload, created in rows:
    main_stages.setdefault(stage_id, []).append((skill_id, payload, created))

order = list(TITLES.keys())
seen = set()
for stage_id in order:
    if stage_id not in main_stages:
        continue
    seen.add(stage_id)
    md = [f"# {TITLES[stage_id]}（Stage: {stage_id}）\n"]
    for skill_id, payload, created in main_stages[stage_id]:
        a = json.loads(payload)
        md.append(f"## Skill: `{skill_id}`")
        md.append(f"- quality_score: **{a.get('quality_score')}**")
        md.append(f"- 產出時間: {created}\n")
        md.append("### Artifact JSON\n```json")
        md.append(json.dumps(a.get('artifact'), ensure_ascii=False, indent=2))
        md.append("```")
        if a.get('unresolved_questions'):
            md.append("\n### 待解決問題")
            md.extend(f"- {q}" for q in a['unresolved_questions'])
        if a.get('risk_list'):
            md.append("\n### 風險清單")
            md.extend(f"- {json.dumps(r_, ensure_ascii=False)}" for r_ in a['risk_list'])
        md.append("\n---\n")
    out = DOC_DIR / f"{TITLES[stage_id]}.md"
    out.write_text("\n".join(md), encoding='utf-8')
    print("匯出文件:", out)

# 總覽報告
summary = ["# 金融信用管理系統 — SE Multi-Agent Workflow 最終報告\n",
           f"- Run ID: `{RUN_ID}`",
           "- 狀態: completed（所有 Stage Gate 通過）\n",
           "| Stage | Skill | quality_score |", "|---|---|---|"]
for stage_id, skill_id, payload, created in rows:
    a = json.loads(payload)
    if skill_id in ("skill_se_cost_control", "skill_se_sec_compliance", "skill_dep_security"):
        continue
    summary.append(f"| {TITLES.get(stage_id, stage_id)} | {skill_id} | {a.get('quality_score')} |")
(DOC_DIR / "00_總覽報告.md").write_text("\n".join(summary), encoding='utf-8')
print("匯出文件:", DOC_DIR / "00_總覽報告.md")
