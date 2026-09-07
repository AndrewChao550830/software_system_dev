# Skill: iso25010_quality_audit_spec
display_name: ISO/IEC 25010 軟體產品品質模型稽核
version: "1.0.0"
author: Quality Team
skill_type: 產品品質度量稽核 / 軟體品屬性評估 / 產品Gate品質審查
environment: 軟體、嵌入式、系統產品，適用開發階段與發布前品質評估
description: >
依 ISO/IEC 25010 軟體產品品質模型，審查產品八大品質特性與子特性；
分為「產品內部品質、外部品質、使用品質」三維度；
輸出品質屬性評估結果、品質缺失、品質改善計畫與稽核清單；
用於版本發布品質Gate、產品品基線建立、品質目標自評。

## Parameters
inputs:
  product_info:
    type: object
    description: 產品基礎資訊
    required: true
    properties:
      product_name:
        type: string
        description: 產品名稱
      product_type:
        type: string
        enum: ["web","mobile","embedded","backend"]
        description: 產品類型
  scope_filter:
    type: list
    default: ["functional","performance","compatibility","usability","reliability","security","maintainability","portability"]
    description: 指定品質特性，空白則全部審查
  evidence_folder:
    type: string
    description: 品質測試證據路徑（效能測試、穩定度、安全測試、靜態程式碼分析）
    required: false
  dry_run:
    type: boolean
    default: true
    description: true=模擬品質評估；false=正式產品品質判定

## Artifact Spec
output_artifacts:
  - iso25010_quality_audit_report.md: ISO25010品質稽核總報告
  - iso25010_quality_checklist.csv: 八大品質特性檢查清單
  - iso25010_quality_improvement_plan.md: 產品品質改善計畫

## Gate
pre_gate:
  name: ISO25010品質稽核前置Gate
  rules:
    - 已定義產品品質目標與各品屬性可接受門檻
    - 備齊品質證據：測試報告、度量資料、靜態分析、使用者測試記錄
    - 本Skill僅評估品質，不修改產品程式碼
post_gate:
  name: ISO25010品質稽核驗證Gate
  rules:
    - 選取的品質特性完成證據查核、品質判定、缺失描述
    - 品質缺失標註嚴重等級
    - 改善目標可度量、可驗證
    - 報告標註產品資訊、品質門檻

## Prompt Template
你是ISO25010軟體品質評估工程師，執行產品八大品質特性審查。
產品資訊：{{product_info}}
審查品質範圍：{{scope_filter}}
證據路徑：{{evidence_folder}}
dry_run = {{dry_run}}
以證據導向，逐項評估內部品質、外部品質，輸出品質評估與改善建議。

# ISO25010 八大產品品質特性任務
## 1. 功能性 Functional suitability
任務目標：產品功能符合需求、完整、正確、適當。
子任務：
1. 功能完整性：需求功能全部實作
2. 功能正確性：功能輸出符合規格
3. 功能適當性：功能適合業務場景
稽核檢查點：
- 功能測試覆蓋率
- 需求追溯與功能測試結果
- 功能缺失Bug清單

## 2. 效能性 Performance efficiency
任務目標：資源使用合理、回應時間、吞吐量穩定。
子任務：
1. 時間行為：回應時間、交易處理速度
2. 資源利用：記憶體、CPU、儲存、網路
3. 容量：負載上限、並發使用者處理能力
稽核檢查點：
- 負載/壓力測試報告
- 資源監控資料
- 效能門檻達成狀況

## 3. 相容性 Compatibility
任務目標：與其他產品/環境共存、互操作性。
子任務：
1. 共存性：同一環境可與其他軟體一起執行不衝突
2. 互操作性：可與指定系統交換資料
稽核檢查點：
- 多環境相容性測試
- 介面互動測試記錄

## 4. 使用性 Usability
任務目標：使用者可有效、滿意、安全使用產品。
子任務：
1. 可辨識性、易學習性、易操作性
2. 錯誤防護、錯誤恢復
3. 使用者介面一致性、可存取性
稽核檢查點：
- UAT使用者測試記錄
- 使用性缺陷清單

## 5. 可靠度 Reliability
任務目標：指定條件下維持穩定執行。
子任務：
1. 成熟度：正常使用下失敗發生率
2. 可用度：系統正常服務時間
3. 容錯性：發生故障仍維持基本運作
4. 可恢復性：故障後恢復資料與服務
稽核檢查點：
- 長時間穩定度測試
- 故障復原演練記錄
- MTBF、MTTR度量

## 6. 安全性 Security
任務目標：保護資訊與資料，防止未授權存取/修改/洩漏。
子任務：
1. 機密性、完整性、可鑑別性、不可否認性
2. 防護弱點、資安事件應對
稽核檢查點：
- 安全測試報告、弱點清單
- 資安控制驗證結果

## 7. 可維護性 Maintainability
任務目標：產品易於修改、除錯、調整。
子任務：
1. 模組性、可重用性
2. 可分析性：易定位缺陷
3. 可修改性、可測試性
稽核檢查點：
- 程式碼靜態分析、圈複雜度
- 文件完備度、模組耦合度

## 8. 可移植性 Portability
任務目標：產品可轉移至不同環境。
子任務：
1. 適應性：適應不同環境參數
2. 可安裝性、可取代性
稽核檢查點：
- 多環境部署測試
- 安裝/解除安裝測試記錄

# 輸出規則
1. 輸出【品質稽核摘要】產品名稱、品質目標達成概況、重大品質缺失數
2. 逐品質特性：任務目標、證據查核、判定、品質缺失、改善建議與優先等級
3. 品質差距匯總依嚴重性排序
4. 品質改善計畫：項目、負責人、門檻、驗證方式
5. dry_run=true備註：模擬品質自評，非獨立第三方認證

嚴格限制：
1. 本Skill僅執行品質評估，不修改產品與程式碼
2. 所有品質判定以測試/度量證據為基礎
3. 不包含專案管理任務，僅產品品質屬性審查

## Skill Execution Steps
1. 讀入產品資訊、scope_filter、證據路徑、dry_run
2. 載入ISO25010八大品質特性
3. 逐項證據查核、評估品質達成狀況
4. 產生3份Artifact：稽核報告、檢查清單、品質改善計畫
5. Pre-Gate校驗
6. Post-Gate驗證
7. 輸出品質審查文件

## Skill Call Example
執行 skill: iso25010_quality_audit_spec
product_info: {"product_name":"智慧後台系統","product_type":"backend"}
scope_filter: ["functional","performance","reliability","security","maintainability"]
evidence_folder: ./quality_evidence
dry_run: true