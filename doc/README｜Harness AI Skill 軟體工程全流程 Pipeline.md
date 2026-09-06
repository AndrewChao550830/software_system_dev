# 專案的處理流程（Workflow）會依序執行需求分析、建模、架構、實作、測試、部署、可觀測性與回饋迭代等階段，並在每個階段後執行橫向審計（成本控管、安全合規）。每次階段（主 Skill）與橫向審計（cross‑cutting skill）都會呼叫本地 FCC（Free Claude Code）產生結構化 JSON 輸出，並封裝為 Artifact 物件：

# skill\_id：對應執行的 Skill（如 skill\_se\_requirement、skill\_se\_code\_implementation …）

# stage\_id：所屬 workflow 階段（如 requirement、code\_implementation）

# artifact：該 Skill 按 output\_schema 產出的主要內容（JSON 物件）

# unresolved\_questions：尚未解決的問題列表

# risk\_list：風險清單

# quality\_score：0‑100 的品質分數（經 Gate 閘門檢查）

# raw\_llm\_output：LLM 原始回傳文字（方便除錯）

# 所有 Artifact 會被寫入 SQLite 資料庫（artifacts table），並在 Streamlit UI 的「Artifact檢視」頁面以 JSON 形式呈現。因此，專案的處理流程最終產出的是一系列結構化的 Artifact（JSON） artefacts，紀錄每個階段的主要產出、品質分數、未解決問題與風險。這些 Artefact 既是 workflow 中繼資料，也是最終可供審核、除錯或產出報告的成果。

# 說明 「如何把 workflow 產出的結構化 Artifact（JSON） 轉成可用於實際系統開發的文件」，並給出一個可直接執行的範例流程（包括必須先呼叫的 my-code-standard Skill、測試‑驅動開發迴圈、以及產出文件的具體步驟）。

# 

# 1️⃣ 先執行 my‑code‑standard（強制要求）

# 在任何程式碼或文件產生之前，必須先呼叫 my-code-standard 並依照其「需求 → 測試計畫 → 原始碼 → 測試程式 → 執行結果 → 修複日誌」的閉環流程。

# 

# 

# Skill({ skill: "my-code-standard" })

# 這個 Skill 會要求你先撰寫 測試計畫（在此情境下是：驗證產出的設計文件是否完整、正確、可追溯），之後才能寫實作（產文件的腳本），最後再跑測試、記錄修複。

# 

# 2️⃣ 取出所有 Artifact（從 SQLite 讀取）

# 

# \# 範例：utils/artifact\_loader.py

# import sqlite3, json, pathlib

# from typing import List, Dict

# 

# DB\_PATH \= "./db/se\_agent.db"

# 

# def load\_artifacts(run\_id: str) \-\> List\[Dict\]:

#     conn \= sqlite3.connect(DB\_PATH)

#     cur \= conn.cursor()

#     rows \= cur.execute(

#         "SELECT skill\_id, stage\_id, payload FROM artifacts WHERE run\_id=? ORDER BY id",

#         (run\_id,)

#     ).fetchall()

#     conn.close()

#     arts \= \[\]

#     for skill\_id, stage\_id, payload in rows:

#         data \= json.loads(payload)

#         data.update({"skill\_id": skill\_id, "stage\_id": stage\_id})

#         arts.append(data)

#     return arts

# 為什麼要取出所有 Artifact？

# 

# 每個階段的 artifact 欄位就是該階段的主要產出（需求、模型、架構、程式骨架、測試計畫、部署方案、可觀測性設計、迴饋待辦），而 unresolved\_questions、risk\_list、quality\_score 則是品質與風險資訊，後續產文時都會納入說明。

# 

# 3️⃣ 依階段分組並建立文件框架

# workflow 階段 (stage\_id)	對應的產出檔案 (建議檔名)	文件內容大綱

# requirement	docs/01\_需求規格.md	功能需求、非功能需求、使用者故事、驗收標準

# business\_model	docs/02\_業務模型.md	參與者、價值流、收入成本模型

# system\_boundary	docs/03\_C4\_Context.md	C4 Context 圖（可用 dataviz 產）+ 說明

# tech\_design	docs/04\_技術方案與ADR.md	技術選型、架構決策紀錄（ADR）

# data\_state\_design	docs/05\_資料與狀態設計.md	ER 圖、狀態機圖、資料流程

# code\_implementation	src/（程式碼） \+ docs/06\_實作說明.md	程式碼結構、關鍵類別/函式說明、實作重點

# test\_validation	docs/07\_測試計畫.md	單元/整合/驗收測試案例、覆蓋率目標

# deployment	docs/08\_部署手冊.md	環境準備、腳本、容器/VM 配置、滾動更新步驟

# observability	docs/09\_可觀測性設計.md	指標、日誌、追蹤、警報規則、儀表板原型

# feedback\_iteration	docs/10\_迴饋與待辦清單.md	已知問題、風險清單、改進戳記、下一版里程碑

# 每個階段的 artifact（JSON）會直接填入對應小節；unresolved\_questions → 「待決問題」區塊；risk\_list → 「風險與因應措施」區塊；quality\_score → 放在文件開頭的品質儀表板（例如 ⭐ 78/100）。

# 

# 4️⃣ 產出 Markdown 檔案的腳本（可當作一個「文件產生 Skill」）

# 下面是一個可以直接放在 ./skills/doc\_generator/SKILL.md（或任何你偏好的位置）的 Skill 範例。它使用 my-code-standard 的 TDD 步驟：

# 

# 需求：產出完整、可追溯的設計文件。

# 測試計畫：驗證每個必要區塊是否存在、品質分數是否 ≥ 門檻（預設 70）、未解決問題數是否在可接受範圍。

# 原始碼：這裡的「原始碼」是產文的 Python 腳本（見下）。

# 執行結果：跑腳本、檢查產出的 .md 檔案是否符合預期。

# 修複日誌：若測試失敗，記錄原因並修改腳本再跑。

# 4.1 SKILL.md（文件產生 Skill 的說明）

# 

# \---

# name: doc\_generator

# description: |

#   讀取 workflow 產出的 Artifact（JSON），依階段產出對應的設計文件（Markdown），

#   並符合 my-code-standard 的 TDD 閉環。

# input\_schema:

#   type: object

#   properties:

#     run\_id:

#       type: string

#       description: "要產文的 workflow 執行 ID"

#     output\_dir:

#       type: string

#       default: "docs"

#       description: "產出的 Markdown 目錄"

# output\_schema:

#   type: object

#   properties:

#     generated\_files:

#       type: array

#       items:

#         type: string

#       description: "成功產出的檔案路徑清單"

#     summary:

#       type: string

#       description: "簡要說明（例如：'產出 10 個設計文件，品質平均 82'）"

# ...

# 4.2 實作腳本（放在同目錄下的 doc\_generator.py）

# 

# \# skills/doc\_generator/doc\_generator.py

# import json, os, pathlib, re

# from typing import List, Dict, Any

# 

# OUTPUT\_DIR \= "docs"

# 

# def \_safe\_filename(title: str) \-\> str:

#     return re.sub(r'\[\\\\/\*?:"\<\>|\]', "", title).strip().replace(" ", "\_")

# 

# def \_load\_artifacts(run\_id: str) \-\> List\[Dict\]:

#     import sqlite3

#     conn \= sqlite3.connect("./db/se\_agent.db")

#     cur \= conn.cursor()

#     rows \= cur.execute(

#         "SELECT skill\_id, stage\_id, payload FROM artifacts WHERE run\_id=? ORDER BY id",

#         (run\_id,)

#     ).fetchall()

#     conn.close()

#     arts \= \[\]

#     for skill\_id, stage\_id, payload in rows:

#         data \= json.loads(payload)

#         data.update({"skill\_id": skill\_id, "stage\_id": stage\_id})

#         arts.append(data)

#     return arts

# 

# def \_stage\_to\_file(stage\_id: str) \-\> str:

#     mapping \= {

#         "requirement": "01\_需求規格.md",

#         "business\_model": "02\_業務模型.md",

#         "system\_boundary": "03\_C4\_Context.md",

#         "tech\_design": "04\_技術方案與ADR.md",

#         "data\_state\_design": "05\_資料與狀態設計.md",

#         "code\_implementation": "06\_實作說明.md",

#         "test\_validation": "07\_測試計畫.md",

#         "deployment": "08\_部署手冊.md",

#         "observability": "09\_可觀測性設計.md",

#         "feedback\_iteration": "10\_迴饋與待辦清單.md",

#     }

#     return mapping.get(stage\_id, f"{stage\_id}.md")

# 

# def generate\_docs(run\_id: str, output\_dir: str \= OUTPUT\_DIR) \-\> Dict\[str, Any\]:

#     pathlib.Path(output\_dir).mkdir(parents=True, exist\_ok=True)

#     arts \= \_load\_artifacts(run\_id)

# 

#     generated \= \[\]

#     for art in arts:

#         stage \= art.get("stage\_id", "unknown")

#         fname \= \_stage\_to\_file(stage)

#         fpath \= os.path.join(output\_dir, fname)

# 

#         \# 組合 Markdown 內容

#         lines \= \[\]

#         \# 1️⃣ 品質儀表板

#         q \= art.get("quality\_score", 0\)

#         lines.append(f"\#\# 品質分數：{q}/100\\n")

#         \# 2️⃣ 主要產出（artifact）

#         artifact \= art.get("artifact", {})

#         if isinstance(artifact, dict):

#             for k, v in artifact.items():

#                 lines.append(f"\#\#\# {k}")

#                 if isinstance(v, (dict, list)):

#                     lines.append("\`\`\`json")

#                     lines.append(json.dumps(v, ensure\_ascii=False, indent=2))

#                     lines.append("\`\`\`\\n")

#                 else:

#                     lines.append(f"{v}\\n")

#         else:

#             lines.append(f"\`\`\`json\\n{json.dumps(artifact, ensure\_ascii=False)}\\n\`\`\`\\n")

#         \# 3️⃣ 未解決問題

#         uq \= art.get("unresolved\_questions", \[\])

#         if uq:

#             lines.append("\#\#\# 未解決問題")

#             for item in uq:

#                 lines.append(f"- {item}")

#             lines.append("")

#         \# 4️⃣ 風險清單

#         rl \= art.get("risk\_list", \[\])

#         if rl:

#             lines.append("\#\#\# 風險清單")

#             for item in rl:

#                 lines.append(f"- {item}")

#             lines.append("")

#         \# 寫檔

#         with open(fpath, "w", encoding="utf-8") as f:

#             f.write("\\n".join(lines))

#         generated.append(fpath)

# 

#     summary \= f"產出 {len(generated)} 個設計文件，平均品質 {sum(a.get('quality\_score',0) for a in arts)/len(arts):.1f}"

#     return {"generated\_files": generated, "summary": summary}

# 

# \# 若直接執行此腳本（用於除錯）

# if \_\_name\_\_ \== "\_\_main\_\_":

#     import sys

#     run\_id \= sys.argv\[1\] if len(sys.argv) \> 1 else "test-run"

#     res \= generate\_docs(run\_id)

#     print(json.dumps(res, ensure\_ascii=False, indent=2))

# 這段腳本的職責就是「原始碼」步驟；它只依賴 sqlite3 與標準庫，易於在任何環境中執行。

# 

# 4.3 測試計畫（放在同目錄下的 test\_doc\_generator.py）

# 

# \# skills/doc\_generator/test\_doc\_generator.py

# import json, os, shutil, pathlib

# from doc\_generator import generate\_docs

# 

# def test\_generate\_docs\_creates\_expected\_files(tmp\_path):

#     \# 準備一個假的資料庫與少量 Artifact

#     db\_dir \= tmp\_path / "db"

#     db\_dir.mkdir()

#     db\_path \= db\_dir / "se\_agent.db"

#     import sqlite3

#     conn \= sqlite3.connect(db\_path)

#     cur \= conn.cursor()

#     cur.executescript("""

#     CREATE TABLE artifacts (

#         id INTEGER PRIMARY KEY AUTOINCREMENT,

#         run\_id TEXT,

#         skill\_id TEXT,

#         stage\_id TEXT,

#         payload TEXT

#     );

#     """)

#     \# 插入兩筆假資料

#     fake\_art \= {

#         "artifact": {"功能": \["使用者登入", "交易查詢"\]},

#         "unresolved\_questions": \["效能基準未定"\],

#         "risk\_list": \["第三方 API 變動"\],

#         "quality\_score": 85

#     }

#     cur.execute(

#         "INSERT INTO artifacts(run\_id, skill\_id, stage\_id, payload) VALUES (?,?,?,?)",

#         ("run-123", "skill\_se\_requirement", "requirement", json.dumps(fake\_art))

#     )

#     conn.commit()

#     conn.close()

# 

#     \# 切換環境變數讓腳本讀取臨時 DB

#     os.environ\["DB\_PATH"\] \= str(db\_path)

# 

#     \# 執行產文

#     out\_dir \= tmp\_path / "generated\_docs"

#     result \= generate\_docs("run-123", str(out\_dir))

# 

#     \# 斷言

#     assert os.path.isdir(out\_dir)

#     assert len(result\["generated\_files"\]) \== 1

#     generated\_file \= result\["generated\_files"\]\[0\]

#     assert os.path.basename(generated\_file) \== "01\_需求規格.md"

#     content \= pathlib.Path(generated\_file).read\_text(encoding="utf-8")

#     assert "品質分數：85/100" in content

#     assert "使用者登入" in content

#     assert "未解決問題" in content

#     assert "風險清單" in content

# 

#     print("✅ 所有測試通過")

# 這是 測試程式 步驟。若測試失敗，會進入「修複日誌」步驟（檢查錯誤、修正腳本、再次執行測試）。

# 

# 4.4 執行流程（手動或 CI）

# 

# \# 1️⃣ 呼叫 my-code-standard（會強制你先寫測試計畫）

# Skill({ skill: "my-code-standard" })

# 

# \# 2️⃣ 寫好測試（test\_doc\_generator.py）以及實作（doc\_generator.py）

# \# 3️⃣ 執行測試

# python \-m pytest skills/doc\_generator/test\_doc\_generator.py

# \# 4️⃣ 若測試通過，填寫修複日誌（若失敗則回到步驟 2 修正）

# \# 5️⃣ 最終在實務上產出文件：

# python \-m skills.doc\_generator.doc\_generator \<你的 run\_id\>

# 這樣子就完成了 「取得 Artifact → 轉成設計文件」 的完整 Closed‑Loop，且每一步都有對應的測試與品質檢核（quality\_score、未解決問題數、風險清單）會被寫入產出的 Markdown，方便後續的審核、追蹤或自動化文件產管。

# 

# 5️⃣ 產出的文件如何在後續開發中使用？

# 文件類型	典型用途

# 01\_需求規格.md	作為產品待辦清單（Backlog）的來源，直接匯入 Jira / Azure DevOps

# 02\_業務模型.md	幫助架構師確認價值流與成本效益

# 03\_C4\_Context.md	給 UI/UX 團隊畫系統邊界圖，亦可用於威脅建模

# 04\_技術方案與ADR.md	為開發團隊提供技術選型依據，ADR 可作為變更控制的依據

# 05\_資料與狀態設計.md	直接產出 DDL、ORM 模型或資料庫移植腳本

# 06\_實作說明.md	作為程式碼走查的檢核清單，亦可產出 API 文件（Swagger/OpenAPI）

# 07\_測試計畫.md	撰寫單元/整合/驗收腳本的基礎，可與 CI/CD 框架對接

# 08\_部署手冊.md	給 DevOps 團隊建置 K8s Helm chart、Terraform 或腳本

# 09\_可觀測性設計.md	產出 Grafana 監控面板、ELK 日誌規格、警報規則

# 10\_迴饋與待辦清單.md	列出已知問題、風險、改進項目，作為下個 Sprint 的規劃依據

# 每個檔案的開頭都會顯示 品質分數，若分數低於門檻（預設 70）則會在文件最上方加上 ⚠️ 品質不足 的警示標籤，讓審核人員一目了然。

# 

# 6️⃣ 小結：從 Workflow Artifact → 實際系統文件的完整流程

# 呼叫 my-code-standard → 進入 TDD 閉環。

# 寫測試計畫（驗證將要產出的文件必備要素、品質門檻）。

# 實作 doc\_generator.py（讀取 SQLite 中的 Artifact → 產成階段對應的 Markdown）。

# 跑測試 → 若失敗則記錄修複日誌、回到步驟 2‑3，直至全部通過。

# 執行實際產文 → 產出 docs/01\_需求規格.md … 10\_迴饋與待辦清單.md。

# 檢視產出 → 在 Streamlit 的 Artifact 檢視頁或直接開啟 MD 檔確認內容是否完整、品質分數、未解決問題與風險均已正確呈現。

# 提交至版本控制（Git），作為後續開發、評審、合規文件的基礎。

# 這樣一來，你就把原本只存在於資料庫裡的結構化 Artifact 完整轉化為可閱讀、可追蹤、可用於實際系統開發與維護的正式文件，同時仍符合貴團隊的 my-code-standard 品質與流程要求。

# 

# Harness AI Skill 軟體工程全流程 Pipeline

> 專案名稱：SE Full AI Workflow Pipeline ID：`se_full_ai_workflow` 適用：Harness AI Skill / AiSkillStage / AiGate 架構 版本：v0.2.0

## 一、架構總覽

本Pipeline實現**完整軟體開發生命週期（SDLC）**，把每一個工程階段封裝成獨立可複用的AI Skill；每個Stage結尾攜帶 **AiGate審查閘門**，搭配兩支橫切Cross-Cutting Skill（資安合規、成本管控）做全流程穿透式審查。

### 核心設計原則

1. **單一職責Skill**：一個Skill只負責一個階段的產出，低耦合、可單獨測試、可獨立更新。  
2. **Artifact向下流轉**：前序Stage的JSON產物作為`previous_artifacts`輸入後續Stage，保證全流程資訊連續。  
3. **Gate阻斷機制**：每階段必須同時滿足「分數門檻」+「無Critical/High阻斷問題」才可放行。不通過可選擇直接失敗或轉人工審批。  
4. **橫切審查貫穿全流程**：資安、成本不在單獨Stage，而是在每個Gate自動執行，避免後期才發現合規與預算問題。  
5. **閉環回流**：最後回饋迭代Stage可觸發Pipeline從需求階段重新執行，形成持續迭代迴圈。

## 二、完整Pipeline依賴鏈（Stage順序）

需求定義

  ↓

商業模型

  ↓

系統邊界定義

  ↓

系統架構設計

  ↓

技術詳細設計

  ↓

資料狀態設計

  ↓

程式實作

  ↓

測試驗證

  ↓

部署發布

  ↓

可觀測性設計

  ↓

回饋與迭代（可回流至需求階段）

### Skill清單與ID對照表

| Stage名稱 | Skill Identifier | Artifact Type | Gate阻斷欄位 | Gate放行條件 |
| :---- | :---- | :---- | :---- | :---- |
| 需求定義 | `skill_se_requirement` | req\_spec | `blocking_req_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 商業模型 | `skill_se_business_model` | biz\_spec | `blocking_biz_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 系統邊界定義 | `skill_se_system_boundary` | boundary\_spec | `blocking_boundary_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 系統架構設計 | `skill_se_architecture` | arch\_spec | `blocking_arch_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 技術詳細設計 | `skill_se_tech_design` | tech\_spec | `blocking_tech_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 資料狀態設計 | `skill_se_data_state_design` | data\_spec | `blocking_data_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 程式實作 | `skill_se_code_implementation` | code\_artifact | `blocking_code_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 測試驗證 | `skill_se_test_validation` | test\_spec | `blocking_test_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 部署發布 | `skill_se_deployment` | deployment\_spec | `blocking_deploy_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 可觀測性設計 | `skill_se_observability` | observability\_spec | `blocking_obs_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |
| 回饋與迭代 | `skill_se_feedback_iteration` | iteration\_spec | `blocking_iter_issues` | quality\_score ≥70 \+ 阻斷陣列為空 |

> Cross-Cutting Skill（每個Stage Gate都會執行）  
> 

> - `skill_se_sec_compliance`：資安與合規審查  
> - `skill_se_cost_control`：成本與預算審查

## 三、Artifact 資料流說明

### 1\. 全域輸入變數（Pipeline Variables）

1. `project_context`：Object，專案全域上下文  
   - 組織開發規範、資安政策、預算上限、環境定義、SLA標準、維護窗口  
2. `user_input`：String，使用者輸入  
   - 原始需求、商業背景、非功能約束、人工補充澄清資訊

### 2\. previous\_artifacts

每個Stage會接收前面所有Stage的artifact陣列。

> 設計考量：後期階段（如部署、可觀測）需要回溯需求、架構、測試等全部資訊做一致性檢查。 優化選項：大型專案可改為**Artifact Registry儲存+引用ID**，不inline傳遞，避免payload膨脹。

### 3\. 每個Skill標準輸出結構（固定Schema）

所有Skill輸出都包含4個頂層欄位，方便Gate統一取用：

{

  "artifact": {},

  "unresolved\_questions": \[\],

  "risk\_list": \[\],

  "quality\_score": 82

}

- `artifact`：該階段主產物（各階段專屬結構，如req\_spec / deployment\_spec）  
- `unresolved_questions`：待澄清項目，攜帶目標利害關係人  
- `risk_list`：完整風險清單，Critical/High/Medium/Low四級  
- `quality_score`：0\~100，Gate評分判斷基礎

>   
> artifact內部另包含階段專屬的`blocking_xxx_issues`，只存放Critical/High阻斷缺陷。Medium/Low進入risk\_list，不攔截Pipeline。

## 四、AiGate 閘門機制詳解

### Gate判斷規則（每個Stage PostStep）

條件1：quality\_score \>=70

條件2：blocking\_xxx\_issues 陣列長度 \== 0

同時滿足 → 放行下一Stage；任一不滿足 → 觸發failureAction

`failureAction`二選一：

1. `MarkAsFailed`：直接標記Stage失敗，Pipeline終止（預設）  
2. `WaitForApproval`：暫停Pipeline，進入人工審批，可補充資訊重跑該Stage

### CrossCuttingSkills

每個Gate會並行執行資安合規、成本管控兩支橫切Skill，可輸出額外阻斷條件（你可以擴充Gate條件，把cross-cutting的quality\_score也納入判斷）。

> 建議擴充範例（可加進Gate conditions）

\- condition: "\<+crossCuttingOutput.skill\_se\_sec\_compliance.quality\_score\> \>=75"

  failureAction: MarkAsFailed

\- condition: "\<+crossCuttingOutput.skill\_se\_cost\_control.quality\_score\> \>=75"

  failureAction: MarkAsFailed

## 五、回流迭代 Loop 機制

最後Stage `stage_feedback_iteration` 的artifact內 `feedback_loop` 欄位控制回流：

"feedback\_loop": {

  "backflow\_artifact": "req\_spec",

  "trigger\_condition": true

}

Pipeline頂層可加入trigger：

trigger:

  condition: "\<+stage\_feedback\_iteration.steps.step\_skill\_feedback\_iteration.output.artifact.feedback\_loop.trigger\_condition\> \== true"

  rerunPipeline: true

  resetFromStage: stage\_requirement

- 當迭代階段判定「需要更新需求並重新開發」時，自動從需求Stage重新跑完整Pipeline。  
- 回流時，可將`iteration_spec`作為user\_input帶入新一輪Pipeline，傳入產品回饋、缺陷與新待辦。

## 六、部署安裝指引

### 前置依賴

1. Harness Platform 已啟用 AI Skill / AiSkillStage / AiGate 功能  
2. 所有13個Skill（11主流程 \+ 2橫切）已在Harness註冊、版本發布完成，identifier與Pipeline內完全一致  
3. 可選：Artifact Registry，用來儲存各階段JSON產物（大專案推薦）

### 部署步驟

1. 依次匯入所有skill yaml到Harness，檢查每個skill的`identifier`  
2. 匯入 `harness_se_pipeline.yaml`  
3. 設定Pipeline變數schema：`project_context(Object)`、`user_input(String)`  
4. 可視需求調整Gate的failureAction（MarkAsFailed / WaitForApproval）  
5. （可選）開啟回流trigger，啟用迭代loop  
6. 建立Pipeline觸發方式：手動觸發 / Webhook觸發 / 定期排程

### 驗證測試建議

1. 單Skill測試：對每個Skill單獨輸入sample input，驗證輸出JSON符合schema  
2. 單Stage測試：逐Stage跑，確認artifact可正確向下傳遞  
3. 負面案例測試：故意製造Critical阻斷issue，驗證Gate會攔截Pipeline  
4. 回流測試：設定trigger\_condition=true，驗證Pipeline可重置回到需求Stage

## 七、擴充與優化方向

1. **並行Stage**：技術設計與資料狀態設計可改成平行執行，縮短Pipeline執行時間。  
2. 新增更多Cross-Cutting Skill：例如效能審查、可存取性審查、供應鏈漏洞掃描。  
3. 人工介入Step：在特定Stage插入人工核准Step，放在AiSkill與AiGate之間。  
4. 報表匯出：在Pipeline尾端增加Step，匯出全流程風險、待澄清問題、品質分數摘要。  
5. 版本分支：支援多條Feature分支各自執行獨立SE Pipeline。  
6. 成本/資安門檻分階段調整：早期階段門檻可較寬，進入生產相關階段提高審查分數門檻。

## 八、已知限制與備註

1. 當`previous_artifacts`數量多時，inline傳遞會增加payload大小；建議大專案改用Artifact ID參考。  
2. Loop回流會重置後續所有Stage，不會自動保留舊artifact；可自行實作版本快照。  
3. 所有Skill僅做**規劃、分析、產出規格文件與JSON工件**，不會直接執行實際程式部署或修改基礎設施。

## 九、目錄結構建議（Git Repo）

se-ai-skill-pipeline/

├── pipeline/

│   └── harness\_se\_pipeline.yaml

├── skills/

│   ├── skill\_se\_requirement.yaml

│   ├── skill\_se\_business\_model.yaml

│   ├── skill\_se\_system\_boundary.yaml

│   ├── skill\_se\_architecture.yaml

│   ├── skill\_se\_tech\_design.yaml

│   ├── skill\_se\_data\_state\_design.yaml

│   ├── skill\_se\_code\_implementation.yaml

│   ├── skill\_se\_test\_validation.yaml

│   ├── skill\_se\_deployment.yaml

│   ├── skill\_se\_observability.yaml

│   ├── skill\_se\_feedback\_iteration.yaml

│   ├── skill\_se\_sec\_compliance.yaml

│   └── skill\_se\_cost\_control.yaml

├── samples/

│   ├── sample\_project\_context.json

│   └── sample\_user\_input.txt

└── README.md          \# 本檔

---

# 1\. sample\_project\_context.json

> 用途：餵進 pipeline variable `project_context`，代表組織固定規範、政策、預算、環境設定，整個專案生命週期不變（除非組織政策改版）

{

  "org": {

    "company\_name": "揚沛投資控股",

    "sdlc\_version": "v1.0",

    "coding\_standard": "Backend: Python \+ FastAPI, DB: PostgreSQL; Frontend: Vue3",

    "security\_policy": {

      "data\_classification": \["Public", "Internal", "Confidential"\],

      "pii\_encryption\_required": true,

      "owasp\_top10\_mandatory\_check": true,

      "secret\_management": "Vault",

      "allowed\_inbound\_network": \["Corporate VPN", "Internal API Gateway"\]

    },

    "compliance": {

      "regulations": \["ISO27001"\],

      "audit\_cycle\_months": 12

    }

  },

  "finance": {

    "monthly\_budget\_cap": 120000,

    "max\_cloud\_resource\_cost": 80000,

    "cost\_tracking\_tag": "ai-sdlc-demo",

    "reserved\_instance\_preferred": true

  },

  "environments": {

    "dev": {

      "region": "asia-tw",

      "is\_public": false,

      "sla": "best-effort"

    },

    "staging": {

      "region": "asia-tw",

      "is\_public": false,

      "sla": "99.5%"

    },

    "prod": {

      "region": "asia-tw",

      "is\_public": true,

      "sla": "99.9%"

    }

  },

  "quality": {

    "minimum\_test\_coverage": 80,

    "blocker\_severity\_definition": "Critical/High issue blocks release; Medium/Low tracked in risk register",

    "required\_reviewers": 2

  },

  "limits": {

    "max\_pod\_count\_prod": 16,

    "db\_max\_conn": 200

  }

}

# 2\. sample\_user\_input.txt

> 用途：餵進 pipeline variable `user_input`，本次開發需求、商業目標、非功能約束。 直接複製文字放到Harness pipeline變數 `user_input`（String類型）

專案名稱：內部財務報告AI分析服務

產品目標：

建置內部財務資料自動分析API，讓財務與投資團隊可上傳月度帳務、MT940銀行對帳資料，自動產生對帳報表、異常交易偵測、簡易估值指標。

商業背景：

目前財務團隊手動處理多銀行多幣別對帳，耗時且容易發生人工錯誤；本系統優先服務內部營運，不對外部客戶開放。

功能需求：

1\. 檔案上傳：支援MT940匯入、CSV帳務匯入

2\. 自動對帳引擎：比對銀行流水與帳簿記錄，標示差異

3\. 報表匯出：PDF / JSON 財務對帳摘要

4\. 權限控制：角色分級，財務可完整存取，一般使用者唯讀

非功能約束：

1\. 資料：所有財務資料列為Confidential等級，靜態與傳輸皆需加密

2\. 回應時間：API 95%請求 \<2秒；大量批次匯入可容忍10分鐘

3\. 備份：每日自動備份，保留90天

4\. 不允許直接公網暴露API，必須透過內部API Gateway

5\. 預算上限：雲服務月成本不超過 60,000

排除範圍（不在本次迭代實作）：

\- 外部第三方支付整合

\- 手機App介面

\- 實時交易推送（僅批次分析）

風險備註：

財務資料極敏感，任何資料洩露視為重大事件；資料庫禁止直接開放外部存取。

# 3\. 使用說明（Harness Pipeline 填入變數）

1. 開啟 `se_full_ai_workflow` Pipeline  
2. 進入「Variables」頁籤  
3. 建立兩個變數：  
   - `project_context`：Type \= Object，貼上 `sample_project_context.json`  
   - `user_input`：Type \= String，貼上 `sample_user_input.txt` 的全部文字  
4. 手動觸發Pipeline執行

# 4\. 預期執行現象（方便你驗證）

1. Stage 需求定義 → Skill 產出 req\_spec，quality\_score 預期落在80\~90，無 blocking\_req\_issues → Gate放行  
2. 每個Stage Gate自動跑 cross-cutting skill：資安合規、成本審查  
3. 若故意修改測試：例如把cloud預算改成 200000 超過project\_context上限 → `skill_se_cost_control` 會產生阻斷問題，Gate攔截Pipeline  
4. 最後 stage\_feedback\_iteration 會評估是否回流；此範例預設不會觸發loop，你可以手動修改輸出測試回流機制

# 5\. 測試用負面案例（拿來驗證Gate攔截功能）

## 負面 user\_input（會觸發資安阻斷）

專案：財務報告服務

需求：直接把PostgreSQL資料庫開放公網，不需要VPN，方便外部直接連線。

預期：`skill_se_sec_compliance` 產生Critical阻斷，Gate攔截。

## 負面 user\_input（成本超支阻斷）

專案：財務報告服務

雲資源：預計每月雲花費 150000，超過組織120000上限，但仍要部署。

預期：`skill_se_cost_control` 攔截，Gate失敗。

如果你想，我可以接著寫一份**測試案例清單（正面/負面）+ 預期輸出JSON範本**，用來做自動化驗證每一支Skill。

# 🚀 完整啟動步驟（全部本機服務、不碰公網）

> 前提：你的專案資料夾結構已經建好

專案根目錄/

├─ main.py                 \# 前面完整主程式

├─ workflow\_spec.yaml      \# 剛合併好的 DAG 定義檔

├─ .env                    \# 環境變數

├─ skills/                 \# 手動建立資料夾，放入全部12支skill yaml

└─ db/                     \# 程式自動產生，不用手動建

## 1\. 安裝 Python 依賴套件（只需要一次）

在**專案根目錄**開啟終端機（PowerShell / bash）

pip install pydantic python-dotenv pyyaml requests

## 2\. 確認本機 FCC 服務先啟動（最重要！）

> main.py 只呼叫本機 `127.0.0.1:8082` 的 fcc-server，**沒有網路外部呼叫** 開另一個獨立終端視窗，啟動 fcc-server：

fcc-server

確認 log 顯示：`Listening on http://127.0.0.1:8082` ✅ FCC 本機服務**必須先跑起來**，再執行 main.py，否則會連線失敗。

## 3\. 檢查 .env（放在根目錄）

FCC\_BASE\_URL=http://127.0.0.1:8082

FCC\_API\_KEY=freecc

FCC\_MODEL=claude-sonnet-4-20250514

FCC\_FAILOVER\_MODELS=nvidia\_nim/minimaxai/minimax-m3

FCC\_RETRIES=2

FCC\_MAX\_TOKENS=8192

DB\_PATH=./db/se\_agent.db

QUALITY\_THRESHOLD=70

## 4\. 放入所有 skill yaml

`skills/` 資料夾內必須有這12支yaml，缺一不可：

1. skill\_se\_requirement.yaml  
2. skill\_se\_business\_model.yaml  
3. skill\_se\_system\_boundary.yaml  
4. skill\_se\_tech\_design.yaml  
5. skill\_se\_data\_state\_design.yaml  
6. skill\_se\_code\_implementation.yaml  
7. skill\_se\_test\_validation.yaml  
8. skill\_se\_deployment.yaml  
9. skill\_se\_observability.yaml  
10. skill\_se\_feedback\_iteration.yaml  
11. skill\_se\_cost\_control.yaml  
12. skill\_se\_sec\_compliance.yaml

>   
> 如果你還沒有這12支skill內容，**現在不能直接跑main.py**，會報 `Skill id xxx not found`。

## 5\. 啟動 Agent Workflow（回到專案根目錄終端）

python main.py

# 📌 執行流程會發生什麼

1. `init_db()` → 自動建立 `db/se_agent.db` SQLite資料庫  
2. 載入 workflow\_spec.yaml，解析完整DAG  
3. 依序跑每一個 stage：  
   - 執行主Skill  
   - 自動執行2支橫切審計skill（cost / sec）  
   - Gate閘門檢查 quality\_score、重大漏洞阻斷  
4. 如果 Gate不通過 → 拋出 `GatePause`，程式會印出暫停資訊  
     
   🚨 Gate暫停：xxxx  
     
   Run ID: xxxxxxxx, paused\_stage=xxx

>   
> ⚠️ 目前main.py範例是**一次性執行腳本，沒有內建互動式prompt** 遇到 GatePause 暫停時，**不會自動等待輸入就直接結束程式**。 若要繼續（approve / rerun / cancel），你要自己寫一段呼叫 `resume_workflow()` 的程式碼，帶入該run\_id與選擇。

# 🔄 暫停後續跑範例（你可以新增到main.py測試）

\# 放在 \_\_main\_\_ 區塊，GatePause 抓到之後使用

\# resume\_workflow(run\_uuid, wf, "approve", project\_context, user\_input)

\# resume\_workflow(run\_uuid, wf, "rerun", project\_context, user\_input)

\# resume\_workflow(run\_uuid, wf, "cancel", project\_context, user\_input)

# ❌ 常見錯誤排查

1. `Skill id xxx not found` → skills/資料夾缺少對應yaml，或是yaml裡面 `meta.id` 名稱不匹配  
2. Connection refused [http://127.0.0.1:8082](http://127.0.0.1:8082) → fcc-server **沒有啟動**，或是port不是8082，檢查FCC\_BASE\_URL  
3. JSON解析失敗 → FCC模型輸出截斷，會自動重試一次，若一直失敗調高FCC\_MAX\_TOKENS

## 下一步選項，你想要哪一個？

A. 直接輸出全套 **12支skill完整yaml**，放進skills資料夾就可以完整跑 B. 先修改main.py，增加**GatePause後互動輸入選項(A/R/X)**，暫停時直接在終端選擇放行/重跑/中斷 C. 先寫簡單CLI工具，獨立用來 resume 舊run\_id

你選哪一個？  
安全審計發現阻斷型漏洞：\[{'vuln\_id': 'VULN-001', 'severity': 'Critical', 'description': '原始碼中存在硬編碼的資料庫連線密碼，導致未經授權者可直接取得資料庫存取權。'}, {'vuln\_id': 'VULN-002', 'severity': 'High', 'description': '管理員介面缺少多因素認證 (MFA)，增加被竊取憑證後提權風險。'}\]

# ADR: 程式碼階段安全漏洞修復 VULN-001 / VULN-002

## 背景

Code Implementation Stage安全Gate攔截2項高危漏洞。

## 決策

1. 移除原始碼內硬編碼DB密碼，改用環境變數注入憑證；本機/開發環境使用`.env`（加入.gitignore禁止提交），正式環境使用金鑰管理系統。  
2. 管理員介面強制開啟TOTP MFA，MFA未驗證通過時，拒絕所有管理後台請求。

## 風險

- 開發人員本機若不慎提交.env仍有密碼外洩風險，需新增pre-commit掃描硬編碼secret。

## 驗收準則

- 原始碼與git歷史不存在明文資料庫密碼  
- 管理員帳號未綁定MFA無法登入後台

