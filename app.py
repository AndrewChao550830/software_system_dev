import streamlit as st
import yaml
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any
from orchestrator import (
    init_db,
    run_workflow,
    resume_workflow,
    load_workflow_spec,
    load_artifacts,
    Artifact,
    GatePause
)

TEST_CASE_PATH = Path("test_cases.yaml")

# -------------------------- 頁面初始化設定 --------------------------
st.set_page_config(
    page_title="本地SE Agent Workflow控制台",
    layout="wide",
    initial_sidebar_state="expanded"
)
# 初始化資料庫
init_db()
# 載入Workflow定義
wf_spec = load_workflow_spec("workflow_spec.yaml")

# -------------------------- 載入測試案例函式 --------------------------
def load_test_cases() -> List[Dict[str, Any]]:
    if not TEST_CASE_PATH.exists():
        return []
    raw = yaml.safe_load(TEST_CASE_PATH.read_text(encoding="utf-8"))
    return raw.get("test_cases", [])

# -------------------------- 狀態管理 --------------------------
if "current_run_id" not in st.session_state:
    st.session_state.current_run_id = None
if "run_result_artifacts" not in st.session_state:
    st.session_state.run_result_artifacts: List[Artifact] = []
# 人工審批暫停狀態：記錄run_id、暫停stage、訊息與當時的輸入，供審批按鈕續跑
if "gate_pause_info" not in st.session_state:
    st.session_state.gate_pause_info: Dict[str, Any] = {}
# 存放選取的測試案例
if "selected_test_case" not in st.session_state:
    st.session_state.selected_test_case = None

# -------------------------- 側邊欄 --------------------------
with st.sidebar:
    st.header("📋 Workflow 設定")
    st.subheader(wf_spec.name)
    st.caption(wf_spec.description)
    st.divider()
    st.markdown("### Stage 流程順序")
    for idx, stage in enumerate(wf_spec.stages):
        st.markdown(f"{idx+1}. **{stage['name']}** `{stage['stage_id']}`")
    st.divider()
    st.markdown("### 橫切審計Skill")
    for cross in wf_spec.cross_cutting_skills:
        st.code(cross["skill_id"], language="yaml")

# -------------------------- 人工審批面板（Gate暫停時顯示） --------------------------
def _handle_approval(choice: str):
    """處理人工審批：approve/rerun 從暫停點續跑，cancel 中斷"""
    info = st.session_state.gate_pause_info
    try:
        with st.spinner(f"處理審批（{choice}）並繼續執行中…"):
            artifacts = resume_workflow(
                info["run_id"], wf_spec, choice,
                info["project_context"], info["user_input"]
            )
        st.session_state.gate_pause_info = {}
        st.session_state.current_run_id = info["run_id"]
        st.session_state.run_result_artifacts = artifacts
        if choice == "cancel":
            st.warning("🛑 流程已中斷（狀態：failed）。Artifact保留可於下方檢視。")
        else:
            st.success("✅ 審批完成，Workflow執行完畢！切到Artifact檢視頁查看輸出。")
        st.rerun()
    except GatePause as gp:
        # 下一個stage又被攔下：更新暫停資訊，繼續等審批
        st.session_state.gate_pause_info = {
            "run_id": info["run_id"],
            "stage_id": gp.stage_id,
            "skill_id": gp.skill_id,
            "message": gp.message,
            "project_context": info["project_context"],
            "user_input": info["user_input"],
        }
        st.session_state.current_run_id = info["run_id"]
        st.session_state.run_result_artifacts = load_artifacts(info["run_id"])
        st.rerun()
    except Exception as e:
        st.error(f"續跑異常：{str(e)}")

if st.session_state.gate_pause_info:
    info = st.session_state.gate_pause_info
    with st.container(border=True):
        st.error(f"⏸️ **人工審批：Gate閘門攔下 Stage [{info['stage_id']}]（Skill: {info['skill_id']}）**")
        st.markdown(info["message"])
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✅ 放行並繼續", type="primary", use_container_width=True,
                        help="強行放行本Stage，從下一個Stage繼續執行"):
                _handle_approval("approve")
        with c2:
            if st.button("🔁 修正後重跑此Stage", use_container_width=True,
                        help="清除本Stage產出，以相同輸入重新執行本Stage"):
                _handle_approval("rerun")
        with c3:
            if st.button("❌ 中斷流程", use_container_width=True,
                        help="中斷Workflow，狀態設為failed（已產出Artifact保留）"):
                _handle_approval("cancel")

# -------------------------- 主頁面 --------------------------
st.title("🧩 揚沛投資控股 軟體工程多Agent 本地調度控制台")
tab1, tab2, tab3, tab4 = st.tabs(["啟動新Workflow", "Artifact檢視", "原始Workflow規格", "📂 測試案例庫"])

# Tab1：手動輸入啟動流程
with tab1:
    st.subheader("1. 專案上下文設定")
    col1, col2 = st.columns(2)
    with col1:
        proj_name = st.text_input("專案名稱", value="專案投融資管理系統")
        budget = st.number_input("專案預算", min_value=0, value=50000)
    with col2:
        team = st.text_input("開發團隊", value="揚沛開發團隊")
        availability = st.text_input("可用度目標", value="99.9%")
    compliance_text = st.text_area("合規要求（換行分隔）", value="個人資料保護規範")
    compliance_list = [line.strip() for line in compliance_text.splitlines() if line.strip()]
    st.subheader("2. 使用者需求輸入")
    user_prompt = st.text_area(
        "需求描述",
        height=200,
        value="""開發一個專案投融資管理系統，使用者可以輸入交易合約、查交易合約狀態，管理員可以審核交易合約，支援修改條件。"""
    )
    st.subheader("3. 執行")
    start_btn = st.button("🚀 啟動 Workflow", type="primary", disabled=bool(st.session_state.gate_pause_info))
    if start_btn:
        project_context = {
            "project_name": proj_name,
            "team": team,
            "budget": budget,
            "compliance": compliance_list,
            "non_functional_goals": {
                "availability": availability
            }
        }
        new_run_id = str(uuid.uuid4())
        st.info(f"開始執行，Run ID：{new_run_id}")
        try:
            artifacts = run_workflow(new_run_id, wf_spec, project_context, user_prompt)
            st.session_state.current_run_id = new_run_id
            st.session_state.run_result_artifacts = artifacts
            st.success("✅ Workflow執行完畢！切到Artifact檢視頁查看輸出。")
        except GatePause as gp:
            # Gate攔下：記錄暫停資訊，顯示上方人工審批面板
            st.session_state.gate_pause_info = {
                "run_id": new_run_id,
                "stage_id": gp.stage_id,
                "skill_id": gp.skill_id,
                "message": gp.message,
                "project_context": project_context,
                "user_input": user_prompt,
            }
            st.session_state.current_run_id = new_run_id
            st.session_state.run_result_artifacts = load_artifacts(new_run_id)
            st.warning("⏸️ Gate閘門不通過，流程已暫停等待人工審批（見上方審批面板）。")
            st.rerun()
        except Exception as e:
            st.error(f"執行異常：{str(e)}")

# Tab2：瀏覽Artifact
with tab2:
    st.subheader("Artifact 瀏覽器")
    run_id_select = st.text_input("輸入RunID查詢", value=st.session_state.current_run_id or "")
    load_artifact_btn = st.button("載入Artifact")
    if load_artifact_btn and run_id_select:
        loaded_arts = load_artifacts(run_id_select)
        st.session_state.run_result_artifacts = loaded_arts
        st.session_state.current_run_id = run_id_select
    arts = st.session_state.run_result_artifacts
    if not arts:
        st.warning("尚無Artifact，請先執行Workflow或輸入RunID載入")
    else:
        # 按stage分組
        stage_groups: Dict[str, List[Artifact]] = {}
        for art in arts:
            sid = art.stage_id or "uncategorized"
            if sid not in stage_groups:
                stage_groups[sid] = []
            stage_groups[sid].append(art)
        for stage_id, stage_arts in stage_groups.items():
            with st.expander(f"📦 Stage: {stage_id}", expanded=False):
                for art in stage_arts:
                    st.markdown(f"**Skill ID：{art.skill_id}｜Quality Score：{art.quality_score}**")
                    tab_a1, tab_a2, tab_a3 = st.tabs(["Artifact主輸出", "風險與待確認", "LLM原始回傳"])
                    with tab_a1:
                        st.json(art.artifact)
                    with tab_a2:
                        col_r1, col_r2 = st.columns(2)
                        with col_r1:
                            st.markdown("##### 未解決問題")
                            st.json(art.unresolved_questions)
                        with col_r2:
                            st.markdown("##### 風險清單")
                            st.json(art.risk_list)
                    with tab_a3:
                        st.code(art.raw_llm_output, language="json")
                    st.divider()

# Tab3：Workflow原始規格
with tab3:
    st.subheader("Workflow Spec 原始YAML")
    raw_wf_text = Path("workflow_spec.yaml").read_text(encoding="utf-8")
    st.code(raw_wf_text, language="yaml")

# Tab4：測試案例庫（新增）
with tab4:
    st.subheader("📂 測試案例庫（test_cases.yaml）")
    cases = load_test_cases()
    if not cases:
        st.warning("尚未找到測試案例，請在根目錄建立 test_cases.yaml")
    else:
        case_names = [f"{c['case_id']}｜{c['name']}" for c in cases]
        selected_idx = st.selectbox("選擇測試案例", range(len(case_names)), format_func=lambda x: case_names[x])
        selected_case = cases[selected_idx]
        st.session_state.selected_test_case = selected_case

        with st.expander("🔍 案例預覽", expanded=True):
            st.markdown(f"**Case ID**: {selected_case['case_id']}")
            st.markdown(f"**描述**: {selected_case['description']}")
            st.markdown("**專案上下文**:")
            st.json(selected_case["project_context"])
            st.markdown("**需求Prompt**:")
            st.text_area("User Prompt", selected_case["user_prompt"], height=180, disabled=True)

        run_case_btn = st.button("🚀 執行此測試案例", type="primary", disabled=bool(st.session_state.gate_pause_info))
        if run_case_btn:
            project_context = selected_case["project_context"]
            user_prompt = selected_case["user_prompt"]
            new_run_id = str(uuid.uuid4())
            st.info(f"執行案例 {selected_case['case_id']}，Run ID：{new_run_id}")
            try:
                artifacts = run_workflow(new_run_id, wf_spec, project_context, user_prompt)
                st.session_state.current_run_id = new_run_id
                st.session_state.run_result_artifacts = artifacts
                st.success(f"✅ {selected_case['case_id']} 執行完畢！切Artifact頁檢視輸出。")
            except GatePause as gp:
                st.session_state.gate_pause_info = {
                    "run_id": new_run_id,
                    "stage_id": gp.stage_id,
                    "skill_id": gp.skill_id,
                    "message": gp.message,
                    "project_context": project_context,
                    "user_input": user_prompt,
                }
                st.session_state.current_run_id = new_run_id
                st.session_state.run_result_artifacts = load_artifacts(new_run_id)
                st.warning("⏸️ Gate閘門不通過，流程暫停等待人工審批。")
                st.rerun()
            except Exception as e:
                st.error(f"案例執行異常：{str(e)}")

    st.divider()
    st.markdown("### 匯入/匯出測試案例（文字貼入）")
    import_text = st.text_area("貼上YAML測試案例內容，覆寫儲存", height=220)
    save_btn = st.button("💾 儲存到 test_cases.yaml")
    if save_btn and import_text.strip():
        try:
            yaml.safe_load(import_text) # validate yaml
            TEST_CASE_PATH.write_text(import_text, encoding="utf-8")
            st.success("已儲存，重新載入頁面讀取新案例")
        except Exception as e:
            st.error(f"YAML格式錯誤，無法儲存：{e}")
