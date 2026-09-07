# Skill: iec62304_medical_sw_spec
display_name: IEC 62304 醫療裝置軟體生命週期稽核
version: "1.0.0"
author: Medical Device SW Process Team
skill_type: 醫材軟體生命週期稽核 / 醫材軟體自評 / 法規前置審查
environment: 醫療器材內嵌軟體、醫療資訊系統，適用FDA/CE醫材開發
description: >
依 IEC 62304:2006 醫療裝置軟體生命週期標準，執行醫材軟體流程稽核；
覆蓋軟體開發流程、軟體風險管理、軟體維護、軟體組態、文件與驗證；
輸出流程符合度、缺失、矯正計畫與稽核清單；
用於醫材軟體階段Gate、內審、CE/FDA認證前置自評。

## Parameters
inputs:
  medsw_info:
    type: object
    description: 醫材軟體基礎資訊
    required: true
    properties:
      sw_name:
        type: string
        description: 醫材軟體名稱
      sw_safety_class:
        type: string
        enum: ["A","B","C"]
        description: IEC62304軟體安全分類A/B/C
  scope_filter:
    type: list
    default: ["planning","requirement","design","implementation","verification","risk","config","maintenance"]
    description: 指定審查流程，空白全部審查
  evidence_folder:
    type: string
    description: 醫材軟體證據路徑（軟體風險檔、需求、設計、測試、配置記錄）
    required: false
  dry_run:
    type: boolean
    default: true
    description: true=模擬稽核；false=正式內審判定

## Artifact Spec
output_artifacts:
  - iec62304_audit_report.md: IEC62304醫材軟體稽核總報告
  - iec62304_checklist.csv: IEC62304逐項稽核清單
  - iec62304_gap_remediation.md: 醫材軟體流程矯正改善計畫

## Gate
pre_gate:
  name: IEC62304稽核前置Gate
  rules:
    - 已定義軟體安全分類A/B/C與軟體邊界
    - 備齊證據：軟體風險管理檔、需求基線、設計、測試、配置、追溯矩陣
    - 本Skill僅審查流程，不修改醫材軟體程式與文件
post_gate:
  name: IEC62304稽核結果驗證Gate
  rules:
    - 選取流程完成證據查核、判定、缺失描述
    - 不符合項標註嚴重等級
    - 矯正措施可驗證，對應醫材軟體安全需求
    - 報告標註軟體安全分類與稽核範圍

## Prompt Template
你是IEC62304醫療軟體流程稽核員，執行醫材軟體生命週期審查。
醫材軟體資訊：{{medsw_info}}
審查範圍：{{scope_filter}}
證據路徑：{{evidence_folder}}
dry_run = {{dry_run}}
依IEC62304逐流程執行證據導向稽核，輸出審查結果。

# IEC62304 醫材軟體生命週期任務
## 5. 軟體開發規劃 Software Development Planning
任務目標：建立軟體生命週期計畫，依安全分類定義活動。
子任務：
1. 定義軟體生命週期模型
2. 依軟體安全分類A/B/C選取適用活動
3. 定義軟體風險管理活動
4. 定義資源、人員、交付物、審查點
5. 計畫變更管控
稽核檢查點：
- 軟體開發計畫書
- 安全分類判定文件
- 階段審查Gate定義

## 6. 軟體需求分析 Software Requirements Analysis
任務目標：定義軟體需求，包含安全需求，可測試、可追溯。
子任務：
1. 收集使用者與系統需求
2. 識別軟體安全需求
3. 需求審查，確認完整、一致、可測試
4. 建立需求追溯起點
稽核檢查點：
- 軟體需求規格，含安全需求
- 需求審查記錄
- 需求追溯矩陣

## 7. 軟體設計 Software Design
任務目標：依需求產生軟體架構與詳細設計，滿足安全需求。
子任務：
1. 軟體架構設計，模組與介面
2. 詳細設計
3. 設計審查，含安全設計審查
4. 設計與需求追溯
稽核檢查點：
- 架構與詳細設計文件
- 安全設計審查記錄
- 設計對需求追溯

## 8. 軟體實作 Software Implementation
任務目標：依設計開發軟體單元，單元驗證。
子任務：
1. 單元開發
2. 單元測試
3. 原始碼審查
4. 配置管理控管程式碼基線
稽核檢查點：
- 單元測試記錄
- 程式碼審查
- 原始碼配置基線

## 9. 軟體整合與軟體驗證 Software Integration & Software Verification
任務目標：整合軟體單元，驗證軟體符合需求。
子任務：
1. 軟體整合計畫
2. 階層式整合
3. 軟體驗證測試，覆蓋安全需求
4. 缺陷追蹤與閉合
稽核檢查點：
- 整合測試、軟體驗證報告
- 安全需求測試覆蓋

## 10. 軟體風險管理 Software Risk Management
任務目標：軟體危害識別、風險分析、風險控制，與ISO14971配合。
子任務：
1. 識別軟體相關危害與危害場景
2. 風險估計、風險評估
3. 定義風險控制措施
4. 驗證風險控制有效性
5. 風險持續監控
稽核檢查點：
- 軟體風險管理檔
- 風險控制驗證證據

## 11. 軟體配置管理 Software Configuration Management
任務目標：控制軟體工作產品版本、基線、變更。
子任務：
1. 識別軟體配置項
2. 建立配置庫、基線管理
3. 變更請求評估與審批
4. 配置狀態記錄、配置審核
稽核檢查點：
- 配置項清單、基線記錄
- 軟體變更追蹤記錄

## 12. 軟體維護 Software Maintenance
任務目標：發布後軟體維護、問題回報、變更評估。
子任務：
1. 軟體問題回報機制
2. 維護變更評估，重新執行風險與驗證
3. 維護版本發布管控
稽核檢查點：
- 客戶問題追蹤
- 維護變更的風險與回歸測試記錄

# 輸出規則
1. 輸出【稽核摘要】軟體名稱、安全分類、整體符合度、重大缺失數
2. 逐流程任務：目標、證據查核、判定、缺失描述、改善建議與優先等級
3. 差距匯總依嚴重性排序
4. 矯正計畫：項目、負責人、期限、驗證方式
5. dry_run=true備註：模擬自評，不等同公告機構審查

嚴格限制：
1. 本Skill僅執行IEC62304軟體生命週期流程稽核，硬體/系統層風險ISO14971另獨立Skill
2. 僅審查建議，不修改軟體與法規文件
3. 判定證據導向，醫材安全相關缺失優先標重大

## Skill Execution Steps
1. 讀入醫材軟體資訊、scope_filter、證據路徑、dry_run
2. 載入IEC62304生命週期流程
3. 逐項證據查核、判定符合度、記錄缺失
4. 產生3份Artifact：稽核報告、檢查清單、矯正計畫
5. Pre-Gate校驗
6. Post-Gate驗證
7. 輸出完整醫材軟體審查文件

## Skill Call Example
執行 skill: iec62304_medical_sw_spec
medsw_info: {"sw_name":"生命監測軟體","sw_safety_class":"B"}
scope_filter: ["planning","requirement","design","verification","risk","config"]
evidence_folder: ./medsw_evidence
dry_run: true