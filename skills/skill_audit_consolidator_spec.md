# Skill Specification: skill_audit_consolidator_spec
## Metadata
- Skill ID: skill_audit_consolidator_spec
- Version: 1.0.0
- Category: Compliance / Audit Aggregator
- Purpose: 彙整多份獨立標準稽核Artifact，產生跨框架合規匯總報告、重疊缺失對照、成熟度評分與矯正優先序清單
- Execution Mode: Post-Audit Consolidation（必須在8支稽核Skill全部執行完畢後執行）
- Compatible Harness Step Type: AiSkill
- Dependencies: 
  - 01_CMMI_DEV
  - 02_CMMI_SVC
  - 03_ISO27001 ISMS
  - 04_OWASP ASVS+Top10
  - 05_ISO25010
  - 06_IEC62304
  - 07_COSO
  - 08_COBIT2019
- Output Artifact Root: ${artifact_output_root}/99_final_consolidated

## Input Schema
```yaml
inputs:
  artifact_base_path: string
  org_name: string
  dry_run: boolean

### Input Description

1. `artifact_base_path`: 根目錄，包含 8 個子資料夾，每個子資料夾對應單一稽核 Stage 輸出成果
   - 01_cmmi_dev
   - 02_cmmi_svc
   - 03_iso27001
   - 04_owasp
   - 05_iso25010
   - 06_iec62304
   - 07_coso
   - 08_cobit
2. `org_name`: 受稽核組織名稱，用於報告抬頭與版頭資訊
3. `dry_run`: 模擬執行旗標。true = 自評模擬（備註標註「非第三方認證稽核」）；false = 正式稽核模式

## Gate / 驗收準則（必須全部滿足才算 Skill Pass）

1. ✅ 成功掃描全部 8 個稽核子目錄，無遺漏框架
2. ✅ 讀取各子資料夾內的稽核結果 JSON/Markdown 檢查清單，解析缺失項目、風險等級、對應控制項
3. ✅ 自動辨識跨框架**重複 / 同源缺失**（同一個流程缺陷同時被多個標準抓出，避免重複計算風險）
4. ✅ 產生統一風險分級：Critical 重大 > High 高 > Medium 中 > Low 低
5. ✅ 輸出完整 Artifact 套件，全部檔案必須寫入 outputArtifactPath 指定路徑
6. ✅ 若 dry_run=true，報告頁首強制加上醒目警示文字，不可省略
7. ✅ 所有缺失項目標註來源框架名稱與原始稽核 ID，可回溯至各 Stage 原始稽核證據

## Execution Instructions（Agent 執行 Prompt）

> 
> 你是跨框架合規稽核彙整引擎。讀取 artifact_base_path 底下 8 套稽核成果，執行下面流程，嚴格依照輸出規格產生報告。
> 
> 
> ### Step 1 載入與解析各框架稽核資料
> 
> 
> 遍歷 artifact_base_path 下 01~08 資料夾，載入每個稽核輸出：
> 
> 
> - 檢查清單（checklist.md/checklist.json）
> - 缺失清單（gap_list.json/findings.md）
> - 成熟度分數（maturity_score.json）
> - 證據索引（evidence_index.csv）
> 
> 
> 每一個 Finding 保留欄位：
> 
> 
> - finding_id
> - standard_framework（來源標準）
> - control_id（控制項編號）
> - risk_level
> - description
> - root_cause_suggestion
> - evidence_link（指向原始 Stage artifact）
> 
> 
> ### Step 2 跨框架同源缺失聚合
> 
> 
> 比對所有 findings，執行相似度比對，合併同源缺陷：
> 
> 
> - 同一業務流程 / 系統缺陷，同時被多個標準檢出 → 標記為【跨框架共通缺失】
> - 保留全部來源標籤，**不刪除原始單框架記錄**，只新增聚合視圖
> - 統一風險等級取「最高風險」（例如同一缺失在 ISO27001 為 High、COBIT 為 Medium，彙整後主風險等級為 High）
> 
> 
> ### Step3 計算全域合規指標
> 
> 
> 輸出總表指標：
> 
> 
> 1. 各框架獨立成熟度分數
> 2. 整體企業合規成熟度加權平均分
> 3. 各風險等級數量統計（Critical/High/Medium/Low）
> 4. 跨框架共通缺失數量
> 5. 未滿足控制項總數、已滿足控制項總數
> 
> 
> ### Step4 矯正行動優先序排序
> 
> 
> 優先序公式：`Priority = RiskLevelWeight × Impact × RemediationEffortInverse`
> RiskLevelWeight：Critical=10, High=7, Medium=4, Low=1
> 輸出矯正清單，包含：建議負責單位、建議完成時限、依賴項目。
> 
> 
> ### Step5 產出 Artifact 套件，全部寫入輸出目錄
> 
> 
> 強制輸出下面全部檔案，不可缺少任一：
> 
> 
> 1. `00_Executive_Summary.md` 高階主管摘要（1 頁版，適合董事會 / 管理層）
> 2. `01_Consolidated_Findings_Report.md` 完整匯總稽核報告
> 3. `02_CrossFramework_Gap_Matrix.csv` 跨標準缺失對照矩陣（可匯入 Excel）
> 4. `03_Risk_Remediation_Plan.csv` 矯正追蹤清單
> 5. `04_Maturity_Scorecard.md` 各框架成熟度計分卡
> 6. `05_Artifact_Index.md` 全量證據與原始報告連結索引
> 7. `consolidator_meta.json` Skill 執行中繼資料（時間戳、dry_run 旗標、掃描框架清單、執行狀態）
> 
> 
> ### Step6 Dry Run 強制標示
> 
> 
> 如果 inputs.dry_run = true，在 `00_Executive_Summary.md` 最頂部插入紅色警示區塊：
> 
> 
> > 
> > ⚠️【DRY RUN｜模擬自評稽核】本報告僅內部自評模擬，**不具第三方認證效力，不可用於對外合規宣告**。正式稽核需設定 dry_run=false 並完成獨立證據驗證。
> 
> 
> ### Step7 結束驗證
> 
> 
> 確認所有 7 個檔案都成功輸出。若任一子目錄缺失稽核成果，在報告中標註警告，**不直接中斷 Skill 執行**，持續完成可讀資料的彙整。

## Output Schema

```
outputs:
  consolidated_report_path: string
  remediation_csv_path: string
  scorecard_path: string
  artifact_index_path: string
  meta_json_path: string
```

- consolidated_report_path：完整匯總報告路徑
- remediation_csv_path：矯正行動計畫 CSV
- scorecard_path：成熟度計分卡
- artifact_index_path：證據索引文件
- meta_json_path：執行中繼資訊 JSON

## Failure Strategy

- 部分子 StageArtifact 缺失：Skill 狀態標為`WARNING`，繼續彙整可取得的資料，報告內標註遺漏項目
- 全部 8 個稽核資料夾完全不存在：Skill 狀態`FAILED`，Gate 不通過
- 檔案寫入權限不足：Skill 狀態`FAILED`

## Tags

- audit
- consolidation
- cross-framework
- compliance
- report-generator