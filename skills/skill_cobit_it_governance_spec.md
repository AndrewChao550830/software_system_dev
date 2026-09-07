# Skill: cobit_it_governance_spec
display_name: COBIT 2019 IT治理稽核
version: "1.0.0"
author: IT Governance Team
skill_type: IT治理稽核 / IT流程自評 / IT與商業目標對齊審查
environment: 企業IT治理、IT風險、IT價值交付，適用內審、IT治理成熟度評估
description: >
依 COBIT 2019 IT治理框架，執行治理系統與4個領域37個管理實務稽核；
領域：Evaluate Direct Monitor(EDM)、Align Plan Organise(APO)、Build Acquire Implement(BAI)、Deliver Support Monitor(DSS)；
輸出IT治理成熟度、流程缺失、改善計畫與稽核清單；
用於IT治理自評、IT內審、IT與商業目標對齊評估。

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
      business_priority:
        type: string
        description: 組織當前商業優先目標
  scope_filter:
    type: list
    default: ["edm","apo","bai","dss"]
    description: COBIT四大領域，可指定子流程
  evidence_folder:
    type: string
    description: IT治理證據路徑（IT目標、IT風險、IT投資、服務、變更記錄）
    required: false
  dry_run:
    type: boolean
    default: true
    description: true=模擬稽核；false=正式IT治理自評判定

## Artifact Spec
output_artifacts:
  - cobit_governance_audit_report.md: COBIT IT治理稽核總報告
  - cobit_process_checklist.csv: COBIT流程稽核清單
  - cobit_gov_gap_remediation.md: IT治理改善計畫

## Gate
pre_gate:
  name: COBIT IT治理稽核前置Gate
  rules:
    - 已定義組織商業目標與IT目標對應關係
    - 備齊證據：IT治理手冊、IT風險、投資、變更、服務、績效報告
    - 本Skill僅審查與建議，不修改IT政策與流程
post_gate:
  name: COBIT稽核結果驗證Gate
  rules:
    - 選取領域與流程完成證據查核、成熟度評估、缺失描述
    - 缺失標註嚴重等級
    - 改善目標連結商業價值、可度量
    - 報告標註組織資訊與稽核範圍

## Prompt Template
你是COBIT2019 IT治理稽核師，執行企業IT治理與流程成熟度審查。
組織資訊：{{org_info}}
審查範圍：{{scope_filter}}
證據路徑：{{evidence_folder}}
dry_run = {{dry_run}}
依COBIT 2019四大領域逐流程證據導向稽核，評估IT治理成熟度，輸出審查結果。

# COBIT2019 四大領域任務
## EDM 評估、引導與監督 Evaluate, Direct and Monitor（治理層）
任務目標：董事會/高階主管層IT治理，引導IT價值、風險、優先次序。
子任務：
1. EDM01 確保治理框架設定
2. EDM02 確保利益相關者價值交付
3. EDM03 確保風險優先管理
4. EDM04 確保資源優先管理
5. EDM05 確保利益相關者承諾
稽核檢查點：
- IT治理手冊、董事會IT議程
- IT價值評估、IT風險報告
- IT資源投資決策記錄

## APO 調整、規劃與組織 Align, Plan and Organise
任務目標：IT策略、組織、預算、品質、風險、資產管理。
子任務：
1. APO01 管理IT管理框架
2. APO02 管理策略
3. APO03 管理企業架構
4. APO04 管理創新
5. APO05 管理資產
6. APO06 管理預算與成本
7. APO07 管理人力資源
8. APO08 管理利害相關者
9. APO09 管理品質
10. APO10 管理供應商
11. APO11 管理風險
12. APO12 管理績效
稽核檢查點：
- IT策略與商業目標對齊
- IT資產、預算、供應商管理記錄
- IT績效度量報告

## BAI 建置、取得與實作 Build, Acquire and Implement
任務目標：IT解決方案建置、取得、變更、發布、配置管理。
子任務：
1. BAI01 管理程式開發與維護
2. BAI02 管理需求定義
3. BAI03 管理方案建置
4. BAI04 管理可用性與容量
5. BAI05 管理組織變更
6. BAI06 管理變更
7. BAI07 管理變更接受度與轉換
8. BAI08 管理知識
9. BAI09 管理資產配置
10. BAI10 管理資料
稽核檢查點：
- IT專案/開發流程、變更管理記錄
- 容量規劃、配置管理、資料管理

## DSS 交付、支援與監督 Deliver, Service and Support
任務目標：IT服務交付、支援、安全、營運、事件與問題管理。
子任務：
1. DSS01 管理營運
2. DSS02 管理服務請求與事件
3. DSS03 管理問題
4. DSS04 管理持續性
5. DSS05 管理安全服務
6. DSS06 管理業務流程控制
稽核檢查點：
- IT服務台、事件/問題追蹤
- 災難回復、業務持續性演練
- IT安全營運控制

# 輸出規則
1. 輸出【IT治理稽核摘要】組織、商業目標、整體IT成熟度、重大缺失數
2. 逐領域/流程：任務目標、證據查核、成熟度評估、缺失描述、改善建議與優先等級
3. 差距匯總依嚴重性排序
4. IT治理改善計畫：項目、負責人、目標效益、驗證指標
5. dry_run=true備註：模擬IT治理自評，非正式第三方COBIT認證

嚴格限制：
1. 本Skill僅COBIT 2019 IT治理稽核，不含COBIT5舊版
2. 僅審查建議，不修改IT政策與組織架構
3. 所有評估證據導向，成熟度0~5級

## Skill Execution Steps
1. 讀入組織資訊、scope_filter、證據路徑、dry_run
2. 載入COBIT四大領域流程
3. 逐流程證據查核，評估成熟度、識別缺失
4. 產生3份Artifact：稽核報告、檢查清單、改善計畫
5. Pre-Gate校驗
6. Post-Gate驗證
7. 輸出完整IT治理審查文件

## Skill Call Example
執行 skill: cobit_it_governance_spec
org_info: {"org_name":"揚沛投資控股","business_priority":"數位平台擴展"}
scope_filter: ["edm","apo","bai","dss"]
evidence_folder: ./cobit_evidence
dry_run: true