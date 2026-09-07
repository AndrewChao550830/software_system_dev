## 關於 Harness `dependsOn` 機制說明

1. `dependsOn` 寫在 stage 層級，接受**Stage identifier 清單**，不是 Stage 名稱，所以使用 `s01_cmmi_dev_audit` 這種 identifier，是 Harness 原生語法。
2. 循序鏈：
`s01_cmmi_dev_audit` → `s02_cmmi_svc_audit` → `s03_iso27001_audit` → `s04_owasp_audit` → `s05_iso25010_audit` → `s06_iec62304_audit` → `s07_coso_audit` → `s08_cobit_audit` → `s09_final_summary`
3. 搭配原有 `failureStrategy.action: Continue`：
   - 就算前一個 Stage 狀態為 Failed/Warning，**仍然會繼續執行後續 Stage**（適合完整跑完所有稽核再看全部缺失）
   - 如果需要「前 Stage 失敗直接停止整個管線」，只要全域變數 `fail_pipeline_on_audit_failure` 改成 `true`，Harness 遇到 Stage 失敗，後續依賴 Stage 就不會觸發
4. 相容 Harness AI Skill 執行器，不需要額外 Plugin。

## Mermaid（可匯入 Draw.io）管線依賴圖

預覽

查看代碼

```
flowchart LR
    A["s01_cmmi_dev_audit<br/>CMMI DEV"] --> B["s02_cmmi_svc_audit<br/>CMMI SVC"]
    B --> C["s03_iso27001_audit<br/>ISO27001"]
    C --> D["s04_owasp_audit<br/>OWASP ASVS+Top10"]
    D --> E["s05_iso25010_audit<br/>ISO25010"]
    E --> F["s06_iec62304_audit<br/>IEC62304"]
    F --> G["s07_coso_audit<br/>COSO 內控"]
    G --> H["s08_cobit_audit<br/>COBIT2019"]
    H --> I["s09_final_summary<br/>Consolidator 彙整報告"]
```
## 設定前置作業（Harness UI 要先建好）

1. **Slack Connector**
   - 建立 Slack Connector，ID：`slack_account_conn`（YAML 內 connectorRef 參考）
   - 給 Bot 權限：發送訊息到目標頻道，開啟 Webhook / Slack App OAuth
2. **Artifact Repository**
   - 建立 Harness Artifact Repository，填入`harness_artifact_repo_ref`變數
   - 前面 AiSkill 的 outputArtifactPath 會自動上傳到此 Repo，Download Step 再取回本地
3. 變數覆寫：
   - `slack_channel`：可在 UI 直接改成`#audit-management`等目標頻道

## 更新後 Mermaid 圖（可匯入 Draw.io）

預覽

查看代碼

```
flowchart LR
    A["s01_cmmi_dev_audit<br/>CMMI DEV"] --> B["s02_cmmi_svc_audit<br/>CMMI SVC"]
    B --> C["s03_iso27001_audit<br/>ISO27001"]
    C --> D["s04_owasp_audit<br/>OWASP ASVS+Top10"]
    D --> E["s05_iso25010_audit<br/>ISO25010"]
    E --> F["s06_iec62304_audit<br/>IEC62304"]
    F --> G["s07_coso_audit<br/>COSO 內控"]
    G --> H["s08_cobit_audit<br/>COBIT2019"]
    H --> I["s09_final_summary<br/>Consolidator<br/>↓Artifact Download<br/>↓Slack通知"]
```

豆包

你的 AI 助理，為每日工作學習提供助力

## 可選強化方向（下一輪）

你可以選擇其中一項繼續擴充：

1. **新增排程觸發器**：每月 1 號凌晨自動跑完整套稽核（Pipeline Trigger Schedule）
2. 加上**條件判斷**：若稽核發現 Critical 等級缺失，Slack 訊息改為緊急紅色警示
3. 新增 Step 把矯正清單自動匯入 Jira 建立 Issue