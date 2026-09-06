# 工作計畫：檢查現況與待修正任務

基於對三份設計架構文件的詳細閱讀，以及對當前專案實作的檢查，以下是尚未滿足需求、等待修正的任務條列：

## 🔴 缺失的核心組件

### 1. 程式碼轉譯技能（Skill Code Renderer） - **最高優先級**
- **問題**：目前工作流程中，`skill_se_code_implementation` 只產出結構化JSON元資料（ artefact），但沒有對應的技能將此JSON轉譯為真實可執行的程式碼
- **參考文件**：`doc\這套 Harness AI Skill 架構產出 JSON 到底是什麼、怎麼用、能不能生出真實可執行腳本.md` 第87-130節
- **所需行動**：
  - 建立 `skills/skill_code_renderer.yaml` 
  - 該技能應該：
    * 輸入：`skill_se_code_implementation` 的 artefact JSON
    * 輸出：實際的程式碼檔案（.py、.sql、測試腳本、設定檔等）
    * 遵守 `configuration_management` 規範（禁止硬編碼敏感資訊）
    * 實作上游的 `acceptance_criteria`
  - 在 `workflow_spec.yaml` 中加入此階段，放在 `code_implementation` 之後、`test_validation` 之前

### 2. My-CODE-Standard 強制執行機制 - **最高優先級**
- **問題**：根據 `.claude\CLAUDE.md` 的強制規定，「在任何程式碼或文件產生之前，必須先呼叫 my-code-standard 並依照其『需求 → 測試計畫 → 原始碼 → 測試程式 → 執行結果 → 修複日誌』的閉環流程」
- **參考文件**：`.claude\CLAUDE.md` 第23-33行
- **目前狀態**：雖然 my-code-standard 技能存在於 `C:\Users\coryc\.claude\skills\my-code-standard\SKILL.md`，但工作流程中並未強制在每個程式實作階段執行此技能
- **所需行動**：
  - 在工作流程中，每個將產出程式碼或文件的階段（特別是 `code_implementation` 和 `skill_code_renderer`）之前，必須先執行 my-code-standard
  - 或將 my-code-standard 整合為工作流程的必要前置條件

## 🟡 工作流程增強

### 3. 缺失的階段依賴關係
- **問題**：檢查當前 `workflow_spec.yaml`，發現某些階段的依賴關係可能不完整
- **參考文件**：`doc\將軟體工程全流程標準化為 AI Agent Harness Skill 架構.md` 第195-200節（技術方案設計的依賴）
- **目前狀態**：
  - `tech_design` 依賴於 `[business_model, system_boundary]` ✓
  - `data_state_design` 依賴於 `[business_model, tech_design]` ✓
  - `code_implementation` 依賴於 `[tech_design, data_state_design]` ✓
  - `test_validation` 依賴於 `[requirement, code_implementation]` → **可能缺少對業務模型的依賴**
- **所需行動**：
  - 評估並可能更新 `test_validation` 的依賴，應該包含 `business_model`（因為測試案例應該基於完整的業務需求）

### 4. 水平審計技能整合
- **問題**：雖然橫切技能（成本控管、安全合規）已定義，但需要確認它們正確地在每個階段之後執行
- **參考文件**：`workflow_spec.yaml` 第9-11行、`doc\將軟體工程全流程標準化為 AI Agent Harness Skill 架構.md` 第76-86節
- **所需行動**：
  - 驗證 orchestrator.py 正確地在每個主要階段之後執行 `skill_se_cost_control` 和 `skill_se_sec_compliance`
  - 確認 Gate 機制正確地考慮了這些橫切技能的結果

## 🟢 品質保證缺口

### 5. 測試驗證階段的實際程式碼測試
- **問題**：目前的 `skill_se_test_validation` 似乎只產出測試案例文件，但沒有實際執行針對真實程式碼的測試
- **參考文件**：`doc\這套 Harness AI Skill 架構產出 JSON 到底是什麼、怎麼用、能不能生出真實可執行腳本.md` 第67-71節
- **所需行動**：
  - 在 `skill_code_renderer` 階段產出實際程式碼後，`test_validation` 應該：
    * 讀取由 `skill_code_renderer` 產出的實際程式碼
    * 執行這些程式碼的單元測試、整合測試
    * 產出測試報告和覆蓋率
  - 這可能需要增強現有的 `skill_se_test_validation` 或建立新的測試執行技能

### 6. 程式碼品質門檻執行
- **問題**：Gate mechanism 檢查 `quality_score_min: 70`，但需要確認這個分數是否正確反映了程式碼的實際品質
- **參考文件**：`workflow_spec.yaml` 第14-17行
- **所需行動**：
  - 確認 `skill_se_code_implementation` 和 `skill_code_renderer` 正確計算並回報 `quality_score`
  - 对于 `skill_code_renderer`，quality_score 應該反映：
    * 產出程式碼的完整度
    * 是否遵守了所有接受標準
    * 是否沒有硬編碼的敏感資訊

## 📋 具體實作步驟

### 階段一：建立程式碼轉譯技能
1. 建立 `skills/skill_code_renderer.yaml` 參考第二文件中的建議
2. 實作對應的轉譯邏輯（可以是 orchestrator 中的工具，或是獨立的 Skill）
3. 確保該技能自身遵守 my-code-standard（寫測試先，然後實作）

### 階段二：更新工作流程
1. 修改 `workflow_spec.yaml`，在 `code_implementation` 之後加入 `code_renderer` 階段
2. 更新依賴關係：`code_renderer` 依賴於 `code_implementation`
3. 更新 `test_validation` 的依賴（如果需要的話）以包含來自 `code_renderer` 的實際程式碼

### 階段三：強化 My-CODE-Standard 執行
1. 在 orchestrator 中加入機制，在任何將產出程式碼或重要文件的階段之前，強制執行 my-code-standard
2. 或修改所有相關的 Skill YAML，在其 core_prompt 中包含 my-code-standard 的要求

### 階段四：驗證和測試
1. 執行完整的工作流程以確保所有階段正常執行
2. 驗證產出的實際程式碼可以正常執行並通過測試
3. 確認品質分數和 Gate 機制正常運作

## ✅ 已完成項目（基於檢查）

- [x] 基本的軟體工程階段技能已實作 (requirement, business_model, system_boundary, tech_design, data_state_design, code_implementation, test_validation, deployment, observability, feedback_iteration)
- [x] 橫切審計技能已實作 (skill_se_cost_control, skill_se_sec_compliance)
- [x] my-code-standard 技能存在於用戶目錄中
- [x] 基本的工作流程定義存在 (workflow_spec.yaml)
- [x] Orchestrator 和 Streamlit UI 基礎實作存在

## 📝 待確認事項

需要進一步檢查：
1. 目前 orchestrator.py 是否正確實作了階段間的 artefact 傳遞
2. 是否已經有某種形式的程式碼轉譯機制（也许在某個自定義腳本中）
3. my-code-standard 在當前工作流程中的實際執行情況