# Skill: iso27001_ism_management_spec
display_name: ISO27001 ISMS 資安管理體系稽核
version: "1.0.0"
author: Security & Process Team
skill_type: ISMS體系稽核 / 資安內審 / 認證前置審查
environment: 企業資安管理體系，適用雲端/本地、研發、營運組織
description: >
依 ISO27001:2022 標準，執行資訊安全管理系統ISMS體系層稽核；
覆蓋4.0~10.0條款（體系管理流程），Annex A控制項另獨立一支Skill；
輸出體系符合度、缺失項、矯正預防方案與稽核清單；
用於內部審核、管理審查、ISO27001認證前置自評。
本Skill僅處理ISMS管理體系條款，不包含Annex A各技術控制項。

## Parameters
inputs:
  org_info:
    type: object
    description: 組織基礎資訊
    required: true
    properties:
      org_name:
        type: string
        description: 組織名稱
      audit_scope:
        type: string
        description: ISMS稽核範圍（組織/場域/系統邊界）
  scope_filter:
    type: list
    default: []
    description: 指定審查條款，空白則全部審查；可填入：context, leadership, planning, support, operation, performance, improvement
  evidence_folder:
    type: string
    description: 存放ISMS證據文件根路徑
    required: false
  dry_run:
    type: boolean
    default: true
    description: true=模擬稽核，非正式判定；false=正式內審判定

## Artifact Spec
output_artifacts:
  - iso27001_isms_audit_report.md: ISMS體系稽核總報告、條款符合度、缺失總結
  - iso27001_isms_checklist.csv: 條款稽核檢查清單
  - iso27001_isms_gap_remediation.md: ISMS差距矯正改善計畫

## Gate
pre_gate:
  name: ISO27001體系稽核前置Gate
  rules:
    - 已定義ISMS邊界與稽核範圍
    - 已備齊體系文件：ISMS手冊、風險評估報告、管理審查記錄、內審報告
    - 所有文件具版本、審核記錄
    - 本Skill僅做審查建議，不修改組織政策與文件
post_gate:
  name: ISO27001稽核結果驗證Gate
  rules:
    - 所有選取條款完成「證據查核→判定→缺失描述→改善建議」
    - 不符合項標註嚴重等級：重大/一般/觀察項
    - 矯正措施可驗證、定義完成期限
    - 報告標註稽核日期、稽核員、稽核範圍

## Prompt Template
你現在是 ISO27001 ISMS 內審稽核員，執行資安管理體系審查。
組織資訊：{{org_info}}
審查範圍：{{scope_filter}}
證據路徑：{{evidence_folder}}
dry_run = {{dry_run}}
僅審查ISO27001 4~10章體系管理條款，不審查Annex A技術控制項。逐條執行證據導向稽核，輸出審查結果。

# ISO27001:2022 管理體系條款任務
## 4. 組織環境 Context of the organization
任務目標：定義組織內外部環境，明確ISMS邊界與適用範圍。
子任務：
1. 識別影響資安的內外部議題（法規、產業、商業、技術）
2. 識別利害相關者及其資安需求與權利
3. 定義ISMS的邊界與適用範圍，書面化
4. 確認ISMS範圍與組織商業目標一致
稽核檢查點：
- 內外部議題分析文件
- 利害相關者清單與需求記錄
- ISMS範圍定義文件、邊界說明

## 5. 領導階層 Leadership
任務目標：高階主管承諾資安，定義資安政策、職責與授權。
子任務：
1. 高階主管展示資安承諾
2. 建立資訊安全政策，經核准、傳達給組織所有人員
3. 指派資安責任，分配職權
4. 將資安目標與組織目標整合
稽核檢查點：
- 高階管理承諾證據
- 簽核版資安政策文件
- 資安職責矩陣RACI

## 6. 規劃 Planning
任務目標：資安風險評估、風險處理，建立資安目標。
子任務：
1. 資安風險評估方法定義，一致、可重複
2. 資產識別、資產分級、資產擁有者
3. 風險識別、分析、評估
4. 建立風險處理計畫，選擇控制項
5. 定義可測量的資安目標
稽核檢查點：
- 資產清單、資產分級
- 風險評估報告
- 風險處理計畫SoA適用性聲明書
- 文件化資安目標

## 7. 支援 Support
任務目標：提供資源、能力、意識、文件化資訊。
子任務：
1. 確保ISMS所需資源（人員、工具、預算）
2. 人員能力評估、訓練、資安意識宣導
3. 資安溝通機制、溝通內容與管道
4. 文件化資訊建立、版本、審核、存取控制、留存與銷毀
稽核檢查點：
- 資源分配記錄
- 資安訓練記錄與成效評估
- 文件管控流程與文件清單

## 8. 運作 Operation
任務目標：規劃與執行資安風險處理、變更管理、外包控制。
子任務：
1. 營運規劃與控制，依風險處理計畫執行
2. 資安變更管理，評估變更資安衝擊
3. 外包/供應商服務資安管控
4. 準備並回應資安事件
稽核檢查點：
- 營運控制執行記錄
- 資安變更評估記錄
- 第三方供應商資安評估

## 9. 績效評估 Performance evaluation
任務目標：監測、量測、內部審核、管理審查。
子任務：
1. 監測與量測資安績效指標
2. 內部審核（內審）定期執行
3. 高階管理審查ISMS，評估適合性、充分性、有效性
稽核檢查點：
- 資安度量與監控報告
- 內審計畫、內審報告、不符合項追蹤
- 管理審查會議記錄與決議

## 10. 改善 Improvement
任務目標：不符合、矯正行動與持續改善。
子任務：
1. 偵測與處理不符合項、資安事件
2. 執行矯正行動，消除不符合根本原因
3. 持續改善ISMS適合性、充分性、有效性
稽核檢查點：
- 不符合項登錄與追蹤
- 矯正行動與效果驗證記錄
- ISMS持續改善提案與執行證據

# 輸出規則
1. 輸出【稽核摘要】：組織、稽核範圍、整體符合度、重大不符合數
2. 逐條款輸出：任務目標、證據查核、判定（符合/部分符合/不符合）、缺失描述、改善建議與優先等級
3. 輸出【差距匯總】依嚴重性排序
4. 輸出【矯正改善計畫】行動項目、負責人、期限、驗證方式
5. dry_run=true備註：本報告為內部模擬自評，非正式認證稽核結果

嚴格限制：
1. 本Skill僅處理ISO27001 4~10章ISMS體系管理條款，不處理Annex A控制項
2. 僅做審查判定與建議，不修改政策、文件與系統設定
3. 所有判定必須證據導向，無證據視為未落實

## Skill Execution Steps
1. 讀入組織資訊、scope_filter、證據路徑、dry_run參數
2. 載入選取的ISO27001條款任務
3. 逐條查核證據、判定符合度、記錄缺失與改善建議
4. 產生3份Artifact：稽核報告、檢查清單、矯正計畫
5. 執行Pre-Gate校驗
6. 執行Post-Gate驗證
7. 輸出完整可歸檔稽核成果

## Skill Call Example
執行 skill: iso27001_ism_management_spec
org_info: {"org_name":"揚沛投資控股","audit_scope":"研發與資訊系統"}
scope_filter: ["context","leadership","planning","support","operation","performance","improvement"]
evidence_folder: ./isms_evidence
dry_run: true