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
    GatePause,
    approve_paused_run,
    rerun_stage,
    abort_workflow,
    save_approval_note
)

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

# -------------------------- 狀態管理 --------------------------
if "current_run_id" not in st.session_state:
    st.session_state.current_run_id = None
if "run_result_artifacts" not in st.session_state:
    st.session_state.run_result_artifacts: List[Artifact] = []
# 人工審批暫停狀態：記錄run_id、暫停stage、訊息與當時的輸入，供審批按鈕續跑
if "gate_pause_info" not in st.session_state:
    st.session_state.gate_pause_info: Dict[str, Any] = {}

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
def _handle_approval(choice: str, note: str):
    """處理人工審批：approve/rerun 從暫停點續跑，cancel 中斷"""
    info = st.session_state.gate_pause_info
    # 儲存審批備註
    if note:
        save_approval_note(info["run_id"], info["stage_id"], note)
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

# 顯示人工審批面板僅當工作流程暫停且卡在skill_se_system_boundary stage時
if st.session_state.gate_pause_info and st.session_state.gate_pause_info.get("skill_id") == "skill_se_system_boundary":
    info = st.session_state.gate_pause_info
    # 取得該 stage 的 artifact 以顯示 quality_score 和門檻
    artifacts = load_artifacts(info["run_id"])
    current_artifact = None
    for art in artifacts:
        if art.stage_id == info["stage_id"]:
            current_artifact = art
            break
    quality_score = current_artifact.quality_score if current_artifact else 0
    threshold = 70.0  # 從 skill_se_system_boundary.yaml 的 threshold_settings.quality_score_min

    with st.container(border=True):
        st.error(f"⏸️ **人工審批：Gate閘門攔下 Stage [{info['stage_id']}]（Skill: {info['skill_id']}）**")
        st.markdown(info["message"])
        st.markdown(f"**品質分數**：{quality_score:.1f} | **門檻**：{threshold} | **結果**：{'未通過' if quality_score < threshold else '通過'}")
        st.text_input("審批備註", key="approval_note", placeholder="請輸入審批備註（可選）")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✅ Approve強制放行", type="primary", use_container_width=True,
                         help="強行放行本Stage，從下一個Stage繼續執行"):
                note = st.session_state.approval_note
                _handle_approval("approve", note)
        with c2:
            if st.button("🔄 Rerun重跑Stage", use_container_width=True,
                         help="清除本Stage產出，以相同輸入重新執行本Stage"):
                note = st.session_state.approval_note
                _handle_approval("rerun", note)
        with c3:
            if st.button("❌ Abort終止Workflow", use_container_width=True,
                         help="中斷Workflow，狀態設為failed（已產出Artifact保留）"):
                note = st.session_state.approval_note
                _handle_approval("cancel", note)

# -------------------------- 主頁面 --------------------------
st.title("🧩 揚沛投資控股 軟體工程多Agent 本地調度控制台")
tab1, tab2, tab3, tab4 = st.tabs(["啟動新Workflow", "Artifact檢視", "程式碼渲染", "原始Workflow規格"])

# Tab1：啟動流程
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

# Tab3：程式碼渲染
with tab3:
    st.subheader("程式碼渲染結果")
    # 檢查是否有 skill_code_renderer 的 artefact
    code_artifacts = [a for a in st.session_state.run_result_artifacts if a.skill_id == "skill_code_renderer"]
    if code_artifacts:
        # 取得第一個（假設每個 run 只有一個）
        artifact = code_artifacts[0]
        rendered_files = artifact.artifact.get("rendered_files", [])
        if rendered_files:
            # 搜尋框
            search_term = st.text_input("🔍 搜尋檔案名稱", placeholder="輸入關鍵字過濾檔案", key="code_search")
            # 過濾檔案列表
            if search_term:
                filtered_files = [f for f in rendered_files if search_term.lower() in f["file_path"].lower()]
            else:
                filtered_files = rendered_files
            # 下拉選單選擇檔案
            file_options = {f["file_path"]: f for f in filtered_files}
            selected_file_path = st.selectbox("選擇檔案進行預覽", options=list(file_options.keys()), key="code_select")
            selected_file = file_options[selected_file_path]
            # 顯示檔案資訊
            st.caption(f"檔案路徑: {selected_file['file_path']} | 大小: {selected_file['size_bytes']} 位元組")
            # 顯示程式碼，包含語法高亮和行號
            st.code(selected_file["content"], language=selected_file["language"], line_numbers=True)
            # 單檔下載按鈕
            st.download_button(
                label=f"💾 下載此檔案",
                data=selected_file["content"],
                file_name=selected_file["file_path"],
                mime="text/plain",
                key="download_single"
            )
            # 原始ZIP下載功能：下載所有渲染檔案
            import io
            import zipfile
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for file in rendered_files:
                    zip_file.writestr(file["file_path"], file["content"])
            zip_buffer.seek(0)
            st.download_button(
                label="📦 下載所有渲染檔案 (ZIP)",
                data=zip_buffer,
                file_name="rendered_files.zip",
                mime="application/zip",
                key="download_zip"
            )
        else:
            st.warning("此 stage 沒有渲染任何檔案。")
    else:
        st.info("尚未執行程式碼渲染 stage，或目前 run 沒有此 stage 的產出。")

# Tab4：Workflow原始規格
with tab4:
    st.subheader("Workflow Spec 原始YAML")
    raw_wf_text = Path("workflow_spec.yaml").read_text(encoding="utf-8")
    st.code(raw_wf_text, language="yaml")