# Skill: owasp_asvs_top10_audit_spec
display_name: OWASP ASVS + Top10 應用程式安全驗證稽核
version: "1.0.0"
author: AppSec Team
skill_type: 應用安全稽核 / WebApp安全檢查 / 安全開發審查
environment: Web、API、移動端應用系統，研發/測試/上線前安全Gate審查
description: >
整合 OWASP ASVS 應用安全驗證標準 + OWASP Top10 風險項目，執行應用程式安全逐項稽核；
依ASVS控制項做技術驗證，同時覆蓋Top10高風險弱點；
輸出應用安全符合度、弱點清單、修復計畫與稽核檢查清單；
用於版本發布Gate、安全審查、SDL安全開發流程驗證。

## Parameters
inputs:
  app_info:
    type: object
    description: 應用程式基礎資訊
    required: true
    properties:
      app_name:
        type: string
        description: 應用名稱
      asvs_level:
        type: string
        enum: ["L1","L2","L3"]
        description: ASVS驗證等級
  scope_filter:
    type: list
    default: ["vulnerability","auth","session","accesscontrol","crypto","inputoutput","errorlog","config","api","data","file"]
    description: 指定稽核模組，預設全部
  evidence_folder:
    type: string
    description: 安全測試證據路徑（掃描報告、滲透測試、程式碼審查記錄）
    required: false
  dry_run:
    type: boolean
    default: true
    description: true=模擬稽核；false=正式安全審查判定

## Artifact Spec
output_artifacts:
  - owasp_audit_report.md: OWASP ASVS+Top10安全稽核總報告
  - owasp_security_checklist.csv: ASVS逐項檢查清單
  - owasp_vuln_remediation_plan.md: 弱點修復排程與驗證計畫

## Gate
pre_gate:
  name: OWASP應用安全稽核前置Gate
  rules:
    - 已定義應用邊界與ASVS目標等級
    - 備齊證據：SAST/DAST掃描報告、程式碼審查、滲透測試、安全設計文件
    - 本Skill僅審查、給予修復建議，不修改程式碼與組態
post_gate:
  name: OWASP稽核結果驗證Gate
  rules:
    - 所有選取安全控制項完成證據查核、判定、弱點描述
    - 弱點標註風險等級：嚴重/高/中/低/資訊
    - 修復方案明確，含驗證方法
    - 報告標註應用資訊、稽核時間、ASVS等級

## Prompt Template
你是OWASP應用安全稽核工程師，執行ASVS與Top10弱點審查。
應用資訊：{{app_info}}
稽核範圍：{{scope_filter}}
證據路徑：{{evidence_folder}}
dry_run = {{dry_run}}
逐項執行證據導向安全審查，輸出弱點與安全控制符合度。

# OWASP ASVS + Top10 稽核任務
## 1. 驗證、授權與身分管理 Authentication
任務目標：確保帳號身分驗證機制安全，防止帳號劫持、暴力破解。
子任務：
1. 驗證密碼策略、複雜度、帳號鎖定機制
2. MFA多因素驗證落實狀況
3. 帳號生命週期管理：開通、停用、刪除
4. 預設帳號、預設密碼檢查
5. 防止認證繞過
稽核檢查點：
- 認證流程設計文件
- 暴力破解防護測試證據
- 預設帳號清查記錄

## 2. 工作階段管理 Session Management
任務目標：安全管理Session，防止Session劫持、固定、洩漏。
子任務：
1. Session ID隨機性、長度、加密
2. Cookie安全屬性 Secure、HttpOnly、SameSite
3. Session逾時機制、登出銷毀Session
4. 登入成功後重新產生Session ID
稽核檢查點：
- Cookie組態檢查證據
- Session劫持測試結果

## 3. 存取控制 Access Control
任務目標：確保使用者只能存取授權資源，防止垂直/水平越權。
子任務：
1. 權限最小權限原則
2. 後端每個API都做存取控制驗證（不可只靠前端隱藏）
3. 角色與權限分離
4. 禁止直接修改參數存取其他使用者資料
稽核檢查點：
- 越權測試記錄
- 權限矩陣

## 4. 輸入驗證與輸出編碼 Input & Output Validation
任務目標：防注入攻擊（SQLi、XSS、Command Injection）。
子任務：
1. 所有來自外部輸入做白名單驗證
2. 輸出至HTML/JS時執行編碼防XSS
3. 使用參數化查詢防SQL注入
4. 檔案上傳驗證檔型、大小、內容檢查
稽核檢查點：
- SAST掃描注入弱點
- XSS測試案例與結果

## 5. 密碼學 Crypto
任務目標：安全使用加密演算法，不使用弱加密與硬編碼金鑰。
子任務：
1. 禁止MD5、SHA1等弱雜湊
2. 敏感資料傳輸使用TLS，最低TLS1.2
3. 金鑰與秘密不寫死在程式碼
4. 敏感資料靜態加密
稽核檢查點：
- 加密演算法審查
- 原始碼秘密掃描結果

## 6. 錯誤處理與日誌 Error & Logging
任務目標：不洩漏詳細系統資訊；保留足夠安全事件日誌。
子任務：
1. 對使用者隱藏堆疊追蹤、資料庫錯誤資訊
2. 記錄登入、存取、權限變更、異常操作
3. 日誌不可被前端使用者修改
4. 日誌保留合規期間
稽核檢查點：
- 錯誤頁面測試
- 安全日誌審查

## 7. 安全組態 Security Configuration
任務目標：硬化伺服器、框架、中介軟體，移除不必要功能。
子任務：
1. 移除預設頁面、範例檔案、除錯模式關閉
2. HTTP安全標頭部署（CSP、X-Frame-Options等）
3. 停用不必要HTTP方法
4. 軟體版本管理、漏洞修補
稽核檢查點：
- HTTP標頭掃描
- 中介軟體組態審查

## 8. API安全 API Security
任務目標：REST/GraphQL API防護，防止未授權存取與API濫用。
子任務：
1. API身分驗證與權限檢查
2. 速率限制防暴力/爬蟲
3. 輸入驗證
4. API文件不洩漏敏感資訊
稽核檢查點：
- API安全測試報告
- Rate limit驗證

## 9. OWASP Top10 高風險弱點覆蓋檢核
子任務：
1. 注入攻擊
2. 失效認證與工作階段管理
3. 敏感資料暴露
4. 外部XML實體XXE
5. 失效存取控制
6. 安全設定錯誤
7. 跨站指令碼XSS
8. 不安全反序列化
9. 使用含已知漏洞元件
10. 不足監控與記錄
稽核檢查點：
- DAST/滲透測試Top10弱點清單
- 弱點追蹤與修復狀態

# 輸出規則
1. 輸出【安全稽核摘要】應用名稱、ASVS等級、總弱點統計（嚴重/高/中/低）
2. 逐安全模組：任務目標、證據、判定、弱點描述、修復建議、風險等級
3. 弱點匯總依風險排序
4. 修復計畫：項目、負責人、截止日、驗證方式
5. dry_run=true備註：模擬安全審查，不等同正式滲透測試報告

嚴格限制：
1. 本Skill僅執行稽核審查，不會主動執行掃描與滲透攻擊
2. 不修改程式、組態、環境
3. 判定以證據導向，無證據視為不符合

## Skill Execution Steps
1. 讀入應用資訊、scope_filter、證據路徑、dry_run
2. 載入ASVS與Top10稽核項目
3. 逐項證據查核、識別弱點、分級
4. 產生3份Artifact：稽核報告、檢查清單、修復計畫
5. Pre-Gate校驗
6. Post-Gate驗證
7. 輸出完整安全審查文件

## Skill Call Example
執行 skill: owasp_asvs_top10_audit_spec
app_info: {"app_name":"後台管理 API","asvs_level":"L2"}
scope_filter: ["auth","session","accesscontrol","crypto","inputoutput","api"]
evidence_folder: ./appsec_evidence
dry_run: true