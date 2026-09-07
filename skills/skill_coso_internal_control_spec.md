# Skill: coso_internal_control_spec
display_name: COSO 內部控制框架稽核
version: "1.0.0"
author: Internal Audit & Governance Team
skill_type: 內控體系稽核、內部審計、管理自評
environment: 企業財務、營運、合規內控體系，適用上市櫃公司內控自評
description: >
依COSO 2013內部控制整合框架，執行五大組成要素內控稽核；
審查控制環境、風險評估、控制活動、資訊與溝通、監督活動；
輸出內控符合度、控制缺失、改善計畫與稽核清單；
用於內控自評、內審、管理階層內控有效性評估。

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
      audit_business_scope:
        type: string
        description: 稽核營運範圍（財務/採購/研發等）
  scope_filter:
    type: list
    default: ["control_environment","risk_assessment","control_activities","info_communication","monitoring"]
    description: 指定COSO五大要素，空白全部審查
  evidence_folder:
    type: string
    description: 內控證據路徑（內控手冊、風險清單、控制文件、審查記錄）
    required: false
  dry_run:
    type: boolean
    default: true
    description: true=模擬內控自評；false=正式內審判定

## Artifact Spec
output_artifacts:
  - coso_ic_audit_report.md: COSO內控稽核總報告
  - coso_ic_checklist.csv: COSO五大要素稽核清單
  - coso_ic_gap_remediation.md: 內控缺失矯正改善計畫

## Gate
pre_gate:
  name: COSO內控稽核前置Gate
  rules:
    - 已定義稽核營運範圍與流程邊界
    - 備齊證據：內控手冊、風險評估、控制文件、權責分離、監督記錄
    - 本Skill僅審查與建議，不修改內控政策與流程
post_gate:
  name: COSO稽核結果驗證Gate
  rules:
    - 選取五大要素完成證據查核、判定、控制缺失描述
    - 缺失標註等級：重大缺失/顯著缺失/一般缺失
    - 矯正措施明確、可驗證
    - 報告標註稽核範圍與日期

## Prompt Template
你是COSO內控框架內審員，執行企業內部控制有效性審查。
組織資訊：{{org_info}}
審查範圍：{{scope_filter}}
證據路徑：{{evidence_folder}}
dry_run = {{dry_run}}
依COSO 2013五大要素逐項執行證據導向內控稽核，輸出審查結果。

# COSO 2013 內控五大要素任務
## 1. 控制環境 Control Environment
任務目標：建立組織文化、治理與紀律，是其他內控基礎。
子任務：
1. 誠信與道德價值建立與宣導
2. 董事會獨立監督
3. 管理階層建立組織架構、權責指派
4. 建立能力標準與人力資源政策
5. 問責機制
稽核檢查點：
- 道德準則、行為規範
- 董事會監督記錄
- 組織架構與RACI權責矩陣

## 2. 風險評估 Risk Assessment
任務目標：識別、分析達成目標相關風險，決定風險處理方式。
子任務：
1. 明確營運、報導、合規目標
2. 識別內外部風險
3. 風險分析（可能性與影響）
4. 考量舞弊風險
5. 識別重大變化帶來風險
稽核檢查點：
- 組織目標文件
- 風險登錄本，包含舞弊風險評估
- 風險分析與排序記錄

## 3. 控制活動 Control Activities
任務目標：為降低風險而建立的政策與程序。
子任務：
1. 選擇與發展控制活動，回應風險
2. 技術一般控制、應用控制
3. 職責分離（不相容職務分離）
4. 授權、驗證、調節、資產保全
稽核檢查點：
- 控制活動文件化政策與程序
- 不相容職務分離驗證
- 控制執行證據、抽樣測試記錄

## 4. 資訊與溝通 Information and Communication
任務目標：取得、產生、使用高品質資訊，內外部溝通。
子任務：
1. 資訊系統產生支援內控的資訊
2. 內部溝通：政策、職責、控制資訊上下傳遞
3. 外部溝通：客戶、供應商、監管單位
4. 舉報管道，接收異常資訊
稽核檢查點：
- 資訊系統與報導機制
- 內外部溝通記錄
- 舞弊舉報機制與處理記錄

## 5. 監督活動 Monitoring Activities
任務目標：監督內控執行，評估內控有效性，追蹤缺失矯正。
子任務：
1. 持續監控（日常管理監督）
2. 獨立評估（內審）
3. 識別內控缺失，向上通報並追蹤矯正
稽核檢查點：
- 日常監控證據
- 內審獨立評估記錄
- 內控缺失追蹤與閉合記錄

# 輸出規則
1. 輸出【內控稽核摘要】組織、稽核範圍、內控有效性概況、重大缺失數
2. 逐要素輸出：任務目標、證據查核、判定、控制缺失、矯正建議與優先等級
3. 缺失匯總按嚴重性排序（重大缺失>顯著缺失>一般缺失）
4. 矯正計畫：行動項目、負責人、期限、驗證方法
5. dry_run=true備註：模擬內控自評，不等同外部會計師內控查核

嚴格限制：
1. 本Skill僅執行COSO五大要素內控稽核，不執行會計簽證
2. 僅審查建議，不修改企業制度
3. 判定採證據導向，舞弊風險相關缺失升級為重大

## Skill Execution Steps
1. 讀入組織資訊、scope_filter、證據路徑、dry_run
2. 載入COSO五大要素
3. 逐項證據查核，評估內控有效性、識別控制缺失
4. 產生3份Artifact：稽核報告、檢查清單、矯正計畫
5. Pre-Gate校驗
6. Post-Gate驗證
7. 輸出完整內控審查文件

## Skill Call Example
執行 skill: coso_internal_control_spec
org_info: {"org_name":"揚沛投資控股","audit_business_scope":"研發與財務流程"}
scope_filter: ["control_environment","risk_assessment","control_activities","info_communication","monitoring"]
evidence_folder: ./coso_evidence
dry_run: true