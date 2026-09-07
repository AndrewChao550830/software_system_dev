# Skill: cmmi_v2_task_spec
display_name: CMMI V2.0 管理任務規範審查
version: "1.0.0"
author: Engineering Process Team
skill_type: 流程審查 / 軟體工程成熟度稽核
environment: 通用軟體研發專案（VSCode / Git / 專案管理平台皆可適用）
description: >
依 CMMI V2.0 標準，對軟體研發專案逐項審查各管理任務是否落實；
輸出各任務的符合度評估、缺失項、改善建議與稽核檢查清單；
用於專案階段Gate審查、內部流程自評、CMMI前置準備。

## Parameters
inputs:
  project_info:
    type: object
    description: 專案基礎資訊
    required: true
    properties:
      project_name:
        type: string
        description: 專案名稱
      project_maturity_target:
        type: string
        enum: ["ML1","ML2","ML3","ML4","ML5"]
        description: 本次審查目標成熟度等級
  scope_filter:
    type: list
    default: []
    description: 指定要審查的任務領域，空白則全部審查；可填入：project, risk, supplier, config, qa, measurement, decision, causal_analysis, org_process
  evidence_folder:
    type: string
    description: 存放審查證據文件的根路徑
    required: false
  dry_run:
    type: boolean
    default: true
    description: true=僅產生稽核報告不執行正式判定；false=輸出正式自評判定結果

## Artifact Spec
output_artifacts:
  - cmmi_task_audit_report.md: CMMI管理任務稽核總報告、各任務符合度、缺失與改善計畫
  - cmmi_task_checklist.csv: 逐項稽核檢查清單，可直接列印/匯入稽核系統
  - cmmi_gap_remediation_plan.md: 差距改善方案，針對不符合項給予可執行動作

## Gate
pre_gate:
  name: 稽核前置檢查 Gate
  rules:
    - 專案已定義目標成熟度等級 project_maturity_target
    - 審查範圍 scope_filter 合法，僅包含CMMI V2.0標準任務領域
    - 審查前已收集專案證據（會議記錄、變更記錄、測試報告、配置項清單、度量資料）
    - 禁止直接修改專案流程文件或程式碼；本Skill僅做審查與建議
post_gate:
  name: 稽核結果驗證 Gate
  rules:
    - 所有CMMI管理任務都已完成「證據→判定→缺失描述」三項填寫
    - 缺失項必須標註嚴重等級：重大/一般/觀察項
    - 改善建議具體可執行，不是空泛文字
    - 輸出報告標註審查日期、審查人員、專案資訊

## Prompt Template
你現在是 CMMI V2.0 流程稽核工程師，執行軟體研發專案的管理任務審查。
專案資訊：{{project_info}}
審查範圍：{{scope_filter}}
證據路徑：{{evidence_folder}}
dry_run = {{dry_run}}

# CMMI V2.0 管理任務（Process Area 管理類，本Skill專注管理任務，不含工程實作任務）
> CMMI V2.0 四大能力域中，本Skill覆蓋【管理管控域 Managing】、【品質支持域 Supporting】、【組織改進域 Improving】下所有管理任務。

## 1. Project Planning 專案規劃
任務目標：建立並維護專案計畫，作為專案執行與管控基準。
必須執行的管理子任務：
1. 估算工作產品與任務規模、工作量、成本、排程
2. 定義專案生命週期、階段與階段Gate
3. 識別專案依存關係（內部/外部、團隊/供應商）
4. 建立專案排程與里程碑
5. 定義專案資源需求：人員、環境、工具、硬體授權
6. 定義專案利益相關者參與計畫
7. 建立專案風險初始清單，整合入專案計畫
8. 專案計畫經審核、獲得承諾後才啟動執行
9. 當範圍/排程/資源重大變更時，重新修訂與重新承諾計畫

稽核檢查點：
- 是否有書面專案計畫
- 規模/工作量估算方法是否一致、可追溯
- 里程碑與Gate明確定義
- 計畫變更流程存在，重大變更重新審批

## 2. Project Monitoring and Control 專案監控與控制
任務目標：監控專案計畫實績，當實績明顯偏離基準時採取矯正行動。
子任務：
1. 持續追蹤排程、工作量、成本、範圍、品質指標
2. 識別計畫與實績的偏差
3. 當偏差超出門檻時，觸發矯正行動
4. 追蹤矯正行動直到關閉
5. 定期專案狀態審查（周/月專案會議）
6. 記錄專案問題、問題分類、負責人、關閉時機

稽核檢查點：
- 定期狀態報告
- 偏差門檻定義
- 矯正措施可追蹤，有開/關單記錄

## 3. Risk Management 風險管理
任務目標：在專案全生命週期持續識別、分析、規劃、監控與處理風險。
子任務：
1. 持續識別技術風險、排程風險、資源風險、需求風險、供應商風險
2. 風險分析：發生機率、影響等級，計算風險等級
3. 制定風險應對策略：迴避、緩解、轉移、接受
4. 建立風險負責人與觸發條件
5. 定期審查風險清單，更新狀態
6. 觸發條件達成時執行應對計畫

稽核檢查點：
- 風險登錄本維護
- 風險評估準則統一
- 高風險項目有明確應對方案

## 4. Supplier Agreement Management 供應商協議管理
任務目標：管理供應商協議，確保供應商交付物滿足專案需求。
子任務：
1. 選擇合格供應商
2. 建立書面供應商協議（範圍、交付物、驗收準則、交付時程）
3. 監控供應商進度、品質、問題
4. 執行交付物驗收
5. 管理供應商變更請求
6. 處理供應商不合項與爭議

稽核檢查點：
- 供應商評選記錄
- 正式協議與驗收準則
- 供應商交付物審查記錄

## 5. Configuration Management 配置管理
任務目標：建立並維護工作產品的完整性，透過版本控制、基線管理、變更管控。
子任務：
1. 識別配置項（程式碼、文件、測試案例、規格、資料庫腳本）
2. 建立配置庫與版本管理系統（Git等）
3. 建立並發布配置基線
4. 管理變更請求CR：提單、評估、審批、實作、驗證
5. 配置狀態記錄與報告
6. 配置審核（物理配置審核/功能配置審核）確保基線一致性

稽核檢查點：
- 配置項清單完整
- 基線發布記錄
- 變更請求可追蹤
- 定期配置審核

## 6. Process and Product Quality Assurance 流程與產品品質保證 PPQA
任務目標：客觀評估流程與工作產品，向管理層通報不符合項。
子任務：
1. 依據標準與流程，客觀審查執行活動
2. 客觀審查工作產品
3. 記錄不符合項
4. 向上通報無法在專案層解決的不符合項
5. 追蹤不符合項直到關閉
6. 定期向相關利害關係人報告QA結果

稽核檢查點：
- QA獨立審查記錄
- 不符合項登錄與追蹤
- 問題升級機制

## 7. Measurement and Analysis 度量與分析
任務目標：開發並維持度量能力，以支援管理資訊決策。
子任務：
1. 定義度量目標，對應商業/專案資訊需求
2. 指定度量項目、收集方法、資料來源
3. 收集與驗證度量資料
4. 分析資料、解讀結果
5. 報告度量結果給決策者

稽核檢查點：
- 度量目標與專案目標連結
- 資料收集規則
- 度量報告用於決策

## 8. Decision Analysis and Resolution 決策分析與解決 DAR
任務目標：使用評估準則，對重要決策執行正式多方案評估。
子任務：
1. 識別需要正式評估的重大決策
2. 建立評估準則（權重、評分方式）
3. 產生多個候選方案
4. 依準則評估各方案
5. 選擇推薦方案，記錄決策理由
6. 審批決策結果

稽核檢查點：
- 重大決策清單
- 評估準則與權重
- 決策理由文件化

## 9. Causal Analysis and Resolution 根本原因分析與解決 CAR（ML4起要求）
任務目標：識別缺陷與問題的根本原因，並採取行動預防再發生。
子任務：
1. 選取要分析的缺陷/重大問題
2. 執行根本原因分析（魚骨圖、5Why等）
3. 提出改善行動
4. 驗證改善效果
5. 將有效改善推廣到其他專案

稽核檢查點：
- 根本原因分析記錄
- 改善效果驗證
- 組織層知識擴散

## 10. Organizational Process Definition 組織流程定義 OPD
任務目標：建立並維護組織標準流程庫、流程資產庫，供所有專案使用。
子任務：
1. 建立組織標準流程集
2. 建立流程裁剪準則（專案可依專案特性裁剪組織標準流程）
3. 建立組織流程資產庫（範本、檢查清單、估算範例、過往專案資料）
4. 維護流程文件與版本
5. 定義流程生命周期模型庫

稽核檢查點：
- 組織流程資產庫存在
- 裁剪規則明確
- 流程資產維護更新機制

## 11. Organizational Training 組織訓練 OT
任務目標：發展人員技能與知識，有效執行組織流程。
子任務：
1. 識別組織與專案訓練需求
2. 建立訓練計畫
3. 執行訓練
4. 評估訓練成效
5. 維護訓練記錄

稽核檢查點：
- 訓練需求分析
- 訓練記錄與成效評估

## 12. Organizational Performance Management 組織績效管理 OPM（ML4起）
任務目標：使用量化績效基線與模型，管理組織與專案績效，達成商業目標。
子任務：
1. 建立組織層量化績效基線
2. 建立流程績效模型
3. 將商業目標轉為流程品質與績效目標
4. 使用量化資訊管理專案、預測結果
5. 識別績效改善機會

稽核檢查點：
- 量化基線與統計模型
- 以數據預測專案結果

## 13. Organizational Process Improvement 組織流程改善 OPI（ML5）
任務目標：持續改進組織流程與技術，提升績效。
子任務：
1. 建立流程改善目標
2. 識別與評估改善提案
3. 試驗改善方案（Pilot）
4. 成功的改善在組織層部署
5. 度量改善帶來的效益

稽核檢查點：
- 改善提案機制
- 試驗與部署記錄
- 效益度量

# 輸出規則
1. 先輸出【稽核摘要】：專案名稱、目標成熟度、整體符合度、重大缺失數
2. 逐項處理每一個CMMI管理任務：
   - 任務名稱與目標
   - 證據清單
   - 判定結果：符合 / 部分符合 / 不符合
   - 缺失描述
   - 改善建議與優先等級
3. 輸出【差距匯總】，按嚴重性排序
4. 輸出【改善計畫】：行動項目、負責人、目標日期、驗證方式
5. dry_run=true 時，備註：本報告為自評模擬，不具正式CMMI評估效力

> 限制：
> 1. 本Skill僅處理CMMI**管理類任務**，不處理工程實作類（需求開發、技術解決方案、產品整合、驗證、確認等工程PA）
> 2. 本Skill只做稽核審查，不修改任何專案文件、程式碼、專案排程
> 3. 正式CMMI認證評估仍須由CMMI授權主任評估師執行，本Skill僅作內部自評工具

## Skill Execution Steps
1. 讀入輸入參數 project_info, scope_filter, evidence_folder, dry_run
2. 依scope_filter過濾要審查的CMMI管理任務
3. 逐個管理任務，對照提供的證據進行審查
4. 判定每個任務符合度，記錄缺失與改善建議，標註嚴重等級
5. 產生3份Artifact：稽核報告、稽核檢查清單、差距改善計畫
6. 執行Pre-Gate校驗
7. 輸出完整稽核文件
8. 使用者完成改善後，執行Post-Gate驗證

## Skill Call Example
執行 skill: cmmi_v2_task_spec
project_info: {"project_name":"backend_service_v2","project_maturity_target":"ML3"}
scope_filter: ["project","risk","config","qa","measurement","decision"]
evidence_folder: ./project_evidence
dry_run: true