# 這套 Harness AI Skill 架構產出 JSON 到底是什麼、怎麼用、能不能生出真實可執行腳本

> 簡單一句總結： **這個Skill輸出的JSON不是最終可直接執行的程式碼本身，而是「程式實作的元資料規格清單」；但可以做二次轉譯，自動產出真實原始碼、SQL、測試腳本、pre-commit hook等可執行檔。**

我們拆成三層理解：

1. skill\_se\_code\_implementation 輸出 artifact JSON 內涵  
2. JSON 在 Workflow / Harness 內部的**原生用途**（當前架構預設用途）  
3. 額外加一層轉譯Agent/轉譯Script，把JSON → 真實可執行檔（.py / .sql / pre-commit / yaml）

## 一、skill 輸出的 JSON 長什麼樣（精簡範例）

{

  "project\_structure": {"directories":\["src/api","src/db"\],"files":\["src/main.py"\]},

  "api\_endpoints": \[{"method":"POST","path":"/admin/login","handler":"admin\_auth.login"}\],

  "data\_models": \[{"name":"AdminUser","fields":\["id","account","totp\_secret"\]}\],

  "business\_logic": \[{"module":"admin\_auth","function":"verify\_totp","description":"管理員登入強制TOTP驗證"}\],

  "database\_migration": \[{"version":"v001","operation":"create table","sql":"CREATE TABLE admin\_user (...)"}\],

  "error\_handling": {"strategy":"global\_exception","logging":"structured\_json\_log"},

  "testing\_framework": {"framework":"pytest","test\_cases":\["test\_admin\_login\_mfa\_required"\]},

  "configuration\_management": {"provider":"env","variables":\["DB\_CONN\_STR"\]},

  "risk\_list": \[

    {"vuln\_id":"VULN-001","severity":"Critical","description":"原始碼硬編碼DB密碼"},

    {"vuln\_id":"VULN-002","severity":"High","description":"管理介面缺少MFA"}

  \],

  "acceptance\_criteria": \[

    {"criteria\_id":"AC-CODE-001","title":"移除硬編碼密碼","related\_vuln":\["VULN-001"\],...},

    {"criteria\_id":"AC-CODE-002","title":"管理員MFA強制開啟","related\_vuln":\["VULN-002"\],...}

  \],

  "quality\_score": 55

}

這份JSON叫 **Code Implementation Artifact**，是**結構化設計產物，不是原始碼**。

> 裡面存放：專案樹、API清單、資料模型、業務模組、遷移SQL片段、風險清單、驗收準則、分數。 沒有完整的 `.py` 原始碼，只有「要寫什麼、有哪些模組、介面長怎樣」的規格。

## 二、在現有 Harness AI Agent Workflow 裡，JSON 的原生應用（現在就可以跑）

這份JSON會存入Workflow的artifact儲存，作為**後續Stage的輸入**，整個管線串聯：

1. **Gate閘門自動審查（當前最核心用途）** Harness Orchestrator讀取JSON內的`risk_list`、`quality_score`，對照skill內定義的`gate.validation_rules`  
     
   - 偵測到Critical/High漏洞、quality\_score\<70 → Gate返回False，暫停workflow，觸發人工審批  
   - 人工審批可選 approve / rerun / cancel，就是你剛剛看到的互動  
   - `acceptance_criteria` 會往下傳到 `skill_se_test_verification`（測試驗證Stage），測試Skill直接拿這組AC當測試案例產生依據

   

2. **傳遞給下一個Stage：測試驗證 skill\_se\_test\_verification** 測試Agent讀取這份JSON，依據`api_endpoints`、`data_models`、`acceptance_criteria`自動生成：  
     
   - pytest單元測試  
   - API集成測試  
   - 漏洞對應的負面測案例（例如：未綁MFA嘗試登入、程式掃描硬編碼secret）

   

3. **作為審計與追溯產物，存入Artifact / Git**  
     
   - 每一次workflow執行，這份JSON永久留存，記錄當時識別到的漏洞、驗收準則、品質分數  
   - 可以匯出到報表，產生安全審計報告、風險追蹤表，給資安/合規使用

   

4. **resume\_run.py CLI 讀取這個Artifact做人工操作** 你前面開發的 `resume_run.py` 就是讀取workflow artifact，讀`risk_list`、AC，顯示在UI，並觸發rerun。Streamlit UI也是讀這份JSON視覺化展示：專案結構、漏洞清單、驗收準則、品質分數。

>   
> ⚠️ 到這一步：**只有規格、清單、漏洞，還沒有完整可執行的原始碼腳本**。

## 三、擴充：新增「程式碼轉譯Agent」，把這份JSON → 真實可執行腳本（重點）

我們只要在Workflow新增一個獨立Skill（例如`skill_code_renderer`），**拿code\_implementation artifact JSON作輸入，輸出真實原始碼檔案**。

### 轉譯Agent（skill\_code\_renderer）職責

輸入：code\_implementation artifact JSON 輸出：檔案清單，每個檔包含 `file_path` \+ `content`

{

  "generated\_files": \[

    {"file\_path":"src/api/admin\_auth.py", "content":"完整python程式碼，包含TOTP驗證邏輯，不寫死DB密碼"},

    {"file\_path":"src/db/migrations/v001.sql", "content":"CREATE TABLE admin\_user ..."},

    {"file\_path":"tests/test\_admin\_mfa.py", "content":"pytest測試案例"},

    {"file\_path":".pre-commit-config.yaml", "content":"secret掃描hook設定"},

    {"file\_path":".gitignore", "content":"加入.env"}

  \]

}

然後搭配簡單的python檔寫入工具（小utility，放在orchestrator）： 讀取`generated_files`，直接在本機/Git Repo生成對應檔案。

### 完整管線順序（加上轉譯層）

需求理解 → 業務建模 → 技術方案 → 資料結構設計

→ skill\_se\_code\_implementation 【輸出JSON元資料】

→ Gate安全審查（攔截漏洞、暫停、人工審批）

→ skill\_code\_renderer【讀JSON，生成真實程式碼/腳本】

→ skill\_se\_test\_verification【拿AC+原始碼做測試】

→ 部署、監控迭代

## 四、實務上兩種落地模式

### 模式A：輕量（你現在的架構，不改現有skill）

不新增skill，**Streamlit UI / orchestrator內寫一段轉譯prompt**。 當code\_implementation stage完成，在UI增加按鈕「從Artifact產生原始碼」，把整份JSON丟給LLM，一次輸出完整程式包，下載為zip。

> 適合原型、快速驗證，不需要改Harness Skill CRD。

### 模式B：標準管線（正式產品）

新增獨立 `skill_code_renderer`，納入workflow，成為標準Stage。 每次code\_implementation Gate放行後自動跑，自動輸出程式碼，直接commit到Git。

## 五、限制與重要提醒（不要誤解）

1. code\_implementation這個skill**本身不直接產出完整原始碼檔**，設計目標是「結構化規格與風險識別」，避免大模型一次輸出一整包雜亂無結構程式碼，方便Gate自動審查。  
2. 轉譯出來的腳本**仍然需要人工審查**；LLM可能有邏輯缺陷，但可以自動滿足AC約束（例如自動移除硬編碼密碼、加上MFA驗證程式）。  
3. SQL遷移腳本、pre-commit設定這類簡單腳本，轉譯成功率很高；複雜業務模組，人工仍需要微調。

## 六、你可以馬上做的驗證demo

1. 拿前面範例artifact JSON  
2. 寫一段簡單prompt（放到orchestrator/Streamlit按鈕）

請根據下方code implementation artifact，輸出完整原始碼套件：

\- 產出所有列出的檔案，檔路徑對應project\_structure

\- 實作api\_endpoints、data\_models與business\_logic

\- 遵守configuration\_management，使用環境變數，禁止硬編碼資料庫密碼

\- 實作管理員登入MFA驗證

\- 輸出格式為json array，每個物件包含file\_path與content

Artifact: {{json}}

3. LLM回傳檔案陣列，用python寫到本機資料夾。

---

如果你想要，我可以： 方案1：直接寫 `skill_code_renderer.yaml`（符合harness.io/v1 aiSkill CRD，可直接放進管線） 或是 方案2：寫一段獨立python轉譯小工具，輸入artifact json，輸出完整原始碼資料夾（可直接在Streamlit或orchestrator呼叫），你要哪一個？

# 基於 Harness AI Skill \+ Orchestrator \+ Streamlit 整套架構的二次開發指南

> 前提回顧： 核心架構 \= Harness AI Skill YAML 定義檔（各Stage：需求/建模/設計/程式實作/測試…） \+ Python Orchestrator（workflow排程、Gate調用、Artifact持久化） \+ Streamlit UI（視覺化Workflow、Artifact、人工審批介面） 核心產物：**結構化Artifact JSON**，不是直接原始碼；可加 Code Renderer 轉譯為真實腳本。 二次開發分4大方向：新增Skill、修改既有Skill、擴充Orchestrator能力、擴充前端UI；另外還有擴充外部工具集成（SAST、Git、資料庫）。

## 一、先劃分邊界：二次開發能改什麼、不動什麼（最小影響原則）

### ✅ 可擴展/二次開發模組

1. **Skill層（YAML，最常用）**：新增/修改 `aiSkill` CRD yaml，新增Stage、新增Gate驗證規則、調整core\_prompt、更新input/output schema、新增驗收準則。**不需要改Python程式**  
2. **Orchestrator層（orchestrator.py）**：Workflow排程、Artifact儲存、Gate執行器、Skill調度、resume/rerun邏輯、外部工具呼叫（Git、SAST、金鑰管理）  
3. **UI層（Streamlit）**：新增面板、Artifact預覽、匯出功能、按鈕觸發轉譯、報表匯出、風險儀表板  
4. **擴充Skill（例如 code\_renderer）**：新增轉譯Skill，把Artifact JSON輸出成真實程式碼、SQL、測試腳本

### ⚠️ 盡量不要動的核心底層

- Skill CRD 核心schema（`apiVersion: harness.io/v1, kind:aiSkill`），改了所有YAML全部要重寫，盡量沿用現有meta/input\_schema/output\_schema/gate/error\_handler結構  
- Artifact 頂層資料結構（`artifact + quality_score`），一旦變更，所有Stage之間資料傳遞會全部斷掉

>   
> 開發原則：**優先改YAML，最後才改程式；優先新增Skill，不要直接修改舊Skill**（版本管理，方便回滾）

# 二、二次開發完整流程（標準開發SOP）

## Step1：需求定義，決定擴展類型

3種常見二次開發場景：

1. **場景A：修改既有Skill**（例如：更新skill\_se\_code\_implementation的Gate驗證規則、新增更多安全檢查項目）  
   - 修改yaml → 版本升級（spec.version從0.2.0 → 0.2.1）  
   - 更新core\_prompt / gate.validation\_rules  
2. **場景B：新增一個全新Skill（推薦，低侵入）** 例如：`skill_code_renderer`、`skill_sast_scan`、`skill_cost_estimate`  
   - 新建獨立YAML，定義input\_schema、output\_schema、core\_prompt、gate  
   - 在workflow定義檔更新pipeline，設定depends\_on前置依賴  
3. **場景C：擴充Orchestrator / Streamlit程式能力** 新增工具：Artifact匯出Zip、呼叫外部SAST API、自動Commit程式碼到Git、連接PostgreSQL儲存workflow紀錄

## Step2：開發 & 單元驗證（YAML優先）

### 2.1 開發新Skill YAML範本（固定模板）

apiVersion: harness.io/v1

kind: aiSkill

metadata:

  name: 程式碼轉譯器

  identifier: skill\_code\_renderer

  description: 讀取code\_implementation artifact，輸出真實原始碼、SQL、設定檔

  tags:

    \- software-engineering

    \- code-generator

spec:

  version: 0.1.0

  skillDefinition:

    meta:

      id: skill\_code\_renderer

      name: 程式碼轉譯器

      description: 接收程式實作元資料Artifact，產生可直接寫入檔案系統的原始碼套件

      version: 0.1.0

      depends\_on: \[skill\_se\_code\_implementation\]

      output\_artifact\_type: code\_source\_package

    input\_schema:

      type: object

      required: \[previous\_artifacts\]

      properties:

        previous\_artifacts:

          type: array

          description: 上游code\_implementation輸出的artifact

    core\_prompt: |

      任務：讀取上游code\_implementation artifact，依project\_structure、api\_endpoints、data\_models生成完整原始碼

      輸出固定JSON結構：\[{"file\_path":"string", "content":"string"}\]

    output\_schema:

      type: object

      required: \[artifact, quality\_score\]

      properties:

        artifact:

          type: object

          properties:

            generated\_files:

              type: array

              items:

                type: object

                required: \[file\_path, content\]

                properties:

                  file\_path:

                    type: string

                  content:

                    type: string

    gate:

      gate\_name: code\_renderer\_gate

      gate\_type: format\_check

      validation\_rules: \[\]

    error\_handler:

      retry\_strategy: 1

      max\_retry\_count: 2

      fallback\_action: mark\_human\_review

### 2.2 更新Workflow Pipeline定義（workflow.yaml）

新增Stage順序、依賴關係，這是Orchestrator讀取的管線定義

workflow\_id: se\_full\_lifecycle

stages:

  \- identifier: skill\_se\_requirement

  \- identifier: skill\_se\_business\_model

  \- identifier: skill\_se\_tech\_design

  \- identifier: skill\_se\_data\_state\_design

  \- identifier: skill\_se\_code\_implementation

  \- identifier: skill\_code\_renderer \# \<--新增Stage，依賴code\_implementation

    depends\_on: skill\_se\_code\_implementation

  \- identifier: skill\_se\_test\_verification

## Step3：本地測試（三層測試）

1. **Schema靜態檢查**：使用yaml \+ json schema驗證工具，檢查input/output schema是否合法（避免Harness調用時報schema錯）  
2. **單Skill隔離測試**：Orchestrator單獨呼叫這個Skill，餵入模擬previous\_artifacts，看輸出JSON是否符合output\_schema、quality\_score是否正常  
3. **端到端Workflow測試**：完整跑一遍pipeline，檢查Artifact向下傳遞、Gate攔截邏輯、人工審批暫停、rerun是否正常  
4. UI驗證：打開Streamlit，確認新Stage、新Artifact在介面正確渲染、按鈕可用

>   
> 測試重點：  
> 

> - Gate攔截是否正常觸發  
> - Artifact在Stage之間傳遞不丟失欄位 任何JSON欄位遺失，會直接導致後續Stage崩潰

## Step4：版本管理與部署

1. Skill YAML全部存入Git，每一次修改升級spec.version，寫CHANGELOG  
2. 匯入方式二選一：  
   - GitOps：Orchestrator自動拉取Git內所有skill yaml（最推薦正式環境）  
   - 手動載入：CLI讀取本地yaml檔載入Harness Skill Registry（開發測試用）  
3. 回滾機制：發現bug，直接切回舊版本yaml

# 三、4個最常見二次開發方向 \+ 實作方式

## 方向1：擴充Gate安全檢查（只改YAML，不用動Python）

例如在code\_implementation gate新增：

- 檢查SQL注入風險  
- 檢查未加密敏感欄位 直接在`gate.validation_rules`追加AC，core\_prompt同步新增風險掃描項目。

>   
> 適合：新增安全規範、合規檢查、成本檢查。**最低成本開發**

## 方向2：新增外部工具集成（修改orchestrator.py）

Orchestrator作為中層，可以新增外部工具呼叫Hook：

1. 在Skill執行前/後，呼叫外部API：SAST掃描、Git API、AWS Secret Manager、Jira、漏洞管理平台  
2. 範例流程：code\_implementation完成 → orchestrator呼叫SAST工具掃描原始碼 → 把SAST結果注入risk\_list，回寫Artifact

>   
> 實作方式：在orchestrator新增`tool_provider` class，在skill lifecycle hook（post\_process）呼叫。**不改變Skill YAML結構**

## 方向3：擴充Streamlit UI

常見擴充功能：

1. Artifact匯出：下載JSON / 匯出Markdown審計報告  
2. Code Renderer按鈕：點擊直接觸發轉譯，把generated\_files寫到本地資料夾，下載zip  
3. 儀表板：歷史workflow風險統計、Critical漏洞數量、各Stage通过率  
4. 人工審批表單：自動填入AC、漏洞清單，支援審批備註、風險豁免登記

## 方向4：新增持久化儲存（orchestrator改寫）

預設可以把workflow/artifact存在JSON檔；二次開發可替換成PostgreSQL

- Workflow狀態表：run\_id、current\_stage、status、created\_at  
- Artifact表：run\_id、skill\_id、artifact\_json、quality\_score

>   
> 好處：長期歷史查詢、審計、多使用者同時執行Workflow

# 四、開發時必須遵守的架構約束（踩坑重點）

1. **Artifact向下相容**：新增欄位只能新增，**不能刪除既有欄位**。若舊Stage輸出欄位移除，下游全部報錯  
2. Skill之間透過`previous_artifacts`鬆耦合，Stage不要直接依賴另一個Skill內部prompt細節，只依賴輸出Artifact Schema  
3. Gate只讀取artifact內固定欄位：`risk_list`、`quality_score`、`acceptance_criteria`，Gate邏輯寫在YAML，不要寫死在Python程式  
4. LLM只負責產出結構化JSON；**業務判斷、檔案寫入、外部API呼叫全部交給orchestrator**，不要把檔案IO放到LLM prompt內

# 五、推薦開發順序（建議由簡到難）

1. 先練習：修改skill\_se\_code\_implementation的Gate，新增1條安全驗證規則（只動yaml）  
2. 接著：新增skill\_code\_renderer.yaml，測試元資料轉成原始碼  
3. 接著：在Streamlit新增按鈕，觸發code render並輸出檔案  
4. 最後：擴充orchestrator，整合SAST/Secret掃描外部工具，把外部掃描結果自動寫入risk\_list

# 六、測試與除錯工具

1. 本機CLI：resume\_run.py，單獨執行/重跑Stage，快速驗證Gate  
2. Streamlit：即時視覺化Artifact、風險清單，人工審批模擬  
3. YAML lint \+ JSON Schema validator：驗證skill yaml語法與schema

---

## 可選的下一步

你可以選其中一個直接開發：

1. 產生 `skill_code_renderer.yaml`（Harness aiSkill完整CRD，直接納入workflow）  
2. 或是，寫 orchestrator 的 tool hook 範例，把 SAST secret掃描整合進管線  
3. 或是，在Streamlit增加「產生原始碼套件並下載ZIP」UI功能

# 交付內容總清單

1. `skill_code_renderer.yaml` 完整 Harness aiSkill CRD（`apiVersion:harness.io/v1`，可直接放進 workflow）  
2. Streamlit 程式補充：新增「產生原始碼套件並下載 ZIP」功能（可直接貼入現有 streamlit app）  
3. workflow.yaml 修改範例（註冊新Stage與依賴）  
4. 完整部署/設定、測試流程與架構說明

---

# 1\. skill\_code\_renderer.yaml（完整 CRD）

apiVersion: harness.io/v1

kind: aiSkill

metadata:

  name: 程式碼轉譯器

  identifier: skill\_code\_renderer

  description: 接收 code\_implementation 的結構化Artifact，轉譯產生完整原始碼、SQL遷移腳本、測試檔、組態檔，輸出檔案清單套件

  tags:

    \- software-engineering

    \- code-generator

    \- artifact-renderer

spec:

  version: 0.1.0

  skillDefinition:

    meta:

      id: skill\_code\_renderer

      name: 程式碼轉譯器

      description: \>

        上游輸入：skill\_se\_code\_implementation 產出的結構化元資料Artifact（專案結構、API、資料模型、業務模組、風險與驗收準則）

        輸出：檔案陣列，包含 file\_path \+ file\_content，後續由 Orchestrator / Streamlit 打包成 ZIP

      version: 0.1.0

      depends\_on: \[skill\_se\_code\_implementation\]

      output\_artifact\_type: code\_source\_package

    input\_schema:

      type: object

      required:

        \- project\_context

        \- previous\_artifacts

      properties:

        project\_context:

          type: object

          description: Harness全域ProjectContext，包含編碼標準、開發框架、語言版本

        previous\_artifacts:

          type: array

          description: 上游Stage產物，必須包含 skill\_se\_code\_implementation 的 artifact

    core\_prompt: |

      【Skill ID: skill\_code\_renderer｜職責：程式碼轉譯】

      任務目標：讀取上游 skill\_se\_code\_implementation 的 artifact，依據專案結構、API定義、資料模型、業務邏輯，生成完整可執行原始碼套件。

      輸入來源：previous\_artifacts 中 code\_implementation artifact，包含 project\_structure、api\_endpoints、data\_models、business\_logic、database\_migration、error\_handling、testing\_framework、configuration\_management、risk\_list、acceptance\_criteria。

      強制約束：

      1\. 嚴格遵守 configuration\_management 規範，所有敏感憑證（DB密碼、金鑰）一律使用環境變數，\*\*禁止硬編碼任何密碼\*\*。

      2\. 必須實作 acceptance\_criteria 定義的驗收規則，例如管理後台MFA/TOTP驗證。

      3\. 依 project\_structure.directories / project\_structure.files 建立對應檔案路徑。

      4\. database\_migration 轉成獨立 .sql 檔。

      5\. testing\_framework 生成對應單元測試檔。

      6\. 產生 .gitignore 與環境範例檔 .env.example，不要產生包含真實密碼的 .env。

      7\. 只輸出純JSON，禁止任何前言、Markdown、\`\`\`標籤、註解。

      \#\# 輸出固定JSON結構

      {

        "generated\_files": \[

          {"file\_path":"string","content":"string"}

        \],

        "render\_note": "string",

        "quality\_score": number

      }

      \- generated\_files：檔案陣列，file\_path為專案內相對路徑；content是完整檔案文字內容

      \- render\_note：轉譯備註，列出風險提醒、人工需要審查的地方

      \- quality\_score：0\~100，代表轉譯完整度，Gate判斷使用

    output\_schema:

      type: object

      required:

        \- artifact

        \- quality\_score

      properties:

        artifact:

          type: object

          properties:

            generated\_files:

              type: array

              description: 原始碼套件檔案列表

              items:

                type: object

                required: \[file\_path, content\]

                properties:

                  file\_path:

                    type: string

                    description: 專案相對檔案路徑

                  content:

                    type: string

                    description: 完整檔案內容

            render\_note:

              type: string

              description: 轉譯備註、人工審查提醒

          required:

            \- generated\_files

            \- render\_note

        quality\_score:

          type: number

          minimum: 0

          maximum: 100

          description: 程式碼轉譯完整度分數

    acceptance\_criteria:

      \- 所有敏感憑證使用環境變數，無硬編碼密碼

      \- 輸出檔案路徑符合上游project\_structure定義

      \- 實作上游acceptance\_criteria中定義的安全驗收項目

      \- 輸出JSON符合schema，generated\_files陣列不可缺失

    gate:

      gate\_name: code\_renderer\_format\_gate

      gate\_type: format\_audit

      description: 檢查轉譯輸出格式、憑證安全規則

      validation\_rules:

        \- criteria\_id: AC-RENDER-001

          title: 禁止硬編碼敏感憑證

          description: 所有輸出程式碼、設定檔中，不可寫死資料庫密碼、API金鑰等敏感資訊，必須採用環境變數。

          check\_method: 內容文字掃描

          pass\_condition: generated\_files內所有檔案不存在明文硬編碼DB密碼、secret金鑰

      failure\_handling:

        action: pause\_workflow

        output\_artifact\_key: artifact

        message\_template: \>

          程式碼轉譯Gate不通過，檢測到憑證安全問題，請重新執行轉譯。

    error\_handler:

      retry\_strategy: 1

      max\_retry\_count: 2

      fallback\_action: mark\_human\_review

      retry\_prompt: "輸出JSON不符合schema，請重新產出嚴格符合輸出結構的純JSON，不要任何額外文字、Markdown與註解"

---

# 2\. 更新 workflow.yaml（加入新Stage）

workflow\_id: se\_full\_lifecycle

workflow\_name: 軟體工程全生命週期管線

stages:

  \- identifier: skill\_se\_requirement

  \- identifier: skill\_se\_business\_model

  \- identifier: skill\_se\_tech\_design

  \- identifier: skill\_se\_data\_state\_design

  \- identifier: skill\_se\_code\_implementation

  \# \===== 新增程式碼轉譯Stage \=====

  \- identifier: skill\_code\_renderer

    depends\_on: skill\_se\_code\_implementation

  \- identifier: skill\_se\_test\_verification

  \- identifier: skill\_se\_deploy

> 管線執行順序：code\_implementation Gate通過後自動執行 skill\_code\_renderer，產生`generated_files`。

---

# 3\. Streamlit UI 擴充：「產生原始碼套件並下載ZIP」

> 依賴套件：`streamlit` \+ `zipfile`（Python內建）+ `io.BytesIO`，不需要額外安裝zip套件。 邏輯：讀取當前 workflow run 的 `skill_code_renderer` artifact → 把 `generated_files` 打包成記憶體ZIP，提供下載按鈕。

## 在你既有 streamlit\_app.py 插入這段程式

import streamlit as st

import zipfile

from io import BytesIO

\# \========= 新增函數：打包 generated\_files 成 ZIP \=========

def package\_source\_zip(generated\_files: list) \-\> BytesIO:

    zip\_buffer \= BytesIO()

    with zipfile.ZipFile(zip\_buffer, "w", zipfile.ZIP\_DEFLATED) as zf:

        for item in generated\_files:

            fp \= item\["file\_path"\]

            content \= item\["content"\]

            zf.writestr(fp, content)

    zip\_buffer.seek(0)

    return zip\_buffer

\# \========= 在Workflow視覺化頁面加入區塊，放在Artifact展示下方 \=========

def render\_code\_renderer\_panel(run\_data):

    st.subheader("📦 程式碼套件管理")

    \# 抓 code\_renderer stage artifact

    code\_render\_stage \= None

    for stage in run\_data\["stages"\]:

        if stage\["skill\_id"\] \== "skill\_code\_renderer":

            code\_render\_stage \= stage

            break

    if not code\_render\_stage:

        st.info("尚未執行 skill\_code\_renderer，請先執行管線到程式碼轉譯Stage")

        return

    stage\_status \= code\_render\_stage\["status"\]

    artifact \= code\_render\_stage.get("artifact", {})

    generated\_files \= artifact.get("generated\_files", \[\])

    render\_note \= artifact.get("render\_note", "")

    if stage\_status \!= "completed":

        st.warning(f"程式碼轉譯Stage狀態：{stage\_status}，無法產生套件")

        return

    st.markdown(f"轉譯備註：{render\_note}")

    st.write(f"共產生 {len(generated\_files)} 個檔案")

    \# 檔案清單預覽

    with st.expander("📄 預覽產出檔案清單"):

        for f in generated\_files:

            st.code(f\["file\_path"\], language="text")

    \# ZIP下載按鈕

    zip\_buf \= package\_source\_zip(generated\_files)

    st.download\_button(

        label="📥 下載原始碼套件 ZIP",

        data=zip\_buf,

        file\_name="source\_package.zip",

        mime="application/zip"

    )

\# \=== 在主Workflow頁面呼叫（找到你原有的run\_data，直接呼叫）===

\# render\_code\_renderer\_panel(run\_data)

## 整合到你的原有Streamlit頁面的位置

找到你Streamlit裡**Workflow Run 詳細頁**，在：

\# 原有程式：展示各Stage、Artifact、Gate結果

\# ...

\# 在Artifact視覺化程式後面加入：

render\_code\_renderer\_panel(run\_data)

> 運作流程：  
> 

> 1. Orchestrator跑完 `skill_code_renderer`，把`generated_files`存入run artifact  
> 2. Streamlit讀取run\_data裡的artifact  
> 3. 點擊按鈕，記憶體打包ZIP，直接瀏覽器下載，**不會寫入伺服器硬碟**

---

# 4\. 完整設定部署步驟

## Step 1：放入Skill YAML到Skill Registry

兩種匯入方式擇一

### 方式A：GitOps（推薦正式環境）

1. 把 `skill_code_renderer.yaml` 和其他所有 skill\_\*.yaml 放進同一Git repo  
2. Orchestrator設定讀取該Git路徑，開機自動載入全部skills  
3. 修改 workflow.yaml 並commit到Git

### 方式B：本地載入（開發測試）

Orchestrator啟動時掃描本地skill資料夾，直接讀取yaml

skills/

 ├─ skill\_se\_requirement.yaml

 ├─ skill\_se\_code\_implementation.yaml

 └─ skill\_code\_renderer.yaml

## Step2：更新 orchestrator.py workflow載入邏輯

確認orchestrator在載入`workflow.yaml`後，會解析`depends_on`，依序排程Stage。

> orchestrator會自動把上游`previous_artifacts`傳入skill\_code\_renderer的input。

## Step3：安裝依賴（Streamlit）

pip install streamlit

> zipfile、BytesIO為Python內建，不需要額外安裝。

## Step4：啟動服務

\# 啟動 Orchestrator

python orchestrator.py

\# 啟動 Streamlit UI

streamlit run streamlit\_app.py

## Step5：端到端測試流程

1. 在Streamlit新建Workflow Run，完整跑管線  
2. 執行到`skill_se_code_implementation`，Gate審查通過  
3. 自動觸發`skill_code_renderer`執行  
4. 轉譯完成，狀態變`completed`  
5. 切到「程式碼套件管理」面板  
6. 預覽檔案清單，點擊下載ZIP，解壓得到完整原始碼專案

---

# 5\. 擴充選項與注意事項

## 5.1 可選增強

1. 在Streamlit增加「直接寫入本機Git倉庫」按鈕（呼叫orchestrator的git工具）  
2. 增加單檔預覽：點擊檔名直接在UI顯示檔案內容  
3. 增加覆蓋保護：檢查本地檔案是否存在，提示覆蓋風險

## 5.2 重要約束

1. skill\_code\_renderer **依賴上游 code\_implementation artifact**，上游Gate不通過就不會執行轉譯  
2. LLM輸出的程式碼依然建議人工審查；Gate僅檢查憑證硬編碼與格式  
3. ZIP是記憶體打包，大型專案（數百檔）需注意記憶體限制，可改成伺服器暫存檔模式  
4. Artifact向下相容：不修改舊skill的輸出schema

## 5.3 除錯檢查清單

- ✅ workflow.yaml 有註冊 skill\_code\_renderer 並設定 depends\_on  
- ✅ skill yaml放對skill資料夾，orchestrator成功載入  
- ✅ code\_implementation stage必須`completed`且Gate放行，才會跑renderer  
- ✅ 檢查run artifact內是否存在`generated_files`陣列  
- ✅ Streamlit可正確讀取run\_data中的stage artifact

---

# 強化 Streamlit 面板：單檔預覽 \+ 語法高亮

## 修改重點

1. 保留原本「下載ZIP」功能  
2. 檔案清單改成可點選下拉選單  
3. 依副檔名自動判斷程式語言，`st.code()` 語法高亮  
4. 增加檔案資訊面板（檔路徑、字數）  
5. 保留轉譯備註、檔案數統計

>   
> 直接替換 / 覆蓋之前的 `render_code_renderer_panel()` 函數即可，無需改動其他既有程式。

import streamlit as st

import zipfile

from io import BytesIO

def package\_source\_zip(generated\_files: list) \-\> BytesIO:

    zip\_buffer \= BytesIO()

    with zipfile.ZipFile(zip\_buffer, "w", zipfile.ZIP\_DEFLATED) as zf:

        for item in generated\_files:

            fp \= item\["file\_path"\]

            content \= item\["content"\]

            zf.writestr(fp, content)

    zip\_buffer.seek(0)

    return zip\_buffer

\# 副檔名對應 streamlit code 語言映射表

def get\_code\_language(file\_path: str) \-\> str:

    ext \= file\_path.lower().split(".")\[-1\]

    lang\_map \= {

        "py": "python",

        "js": "javascript",

        "ts": "typescript",

        "html": "html",

        "css": "css",

        "sql": "sql",

        "yaml": "yaml",

        "yml": "yaml",

        "json": "json",

        "md": "markdown",

        "sh": "bash",

        "bash": "bash",

        "txt": "text",

        "env": "text"

    }

    return lang\_map.get(ext, "text")

def render\_code\_renderer\_panel(run\_data):

    st.subheader("📦 程式碼套件管理")

    \# 抓取 code\_renderer stage

    code\_render\_stage \= None

    for stage in run\_data\["stages"\]:

        if stage\["skill\_id"\] \== "skill\_code\_renderer":

            code\_render\_stage \= stage

            break

    if not code\_render\_stage:

        st.info("尚未執行 skill\_code\_renderer，請先執行管線到程式碼轉譯Stage")

        return

    stage\_status \= code\_render\_stage\["status"\]

    artifact \= code\_render\_stage.get("artifact", {})

    generated\_files \= artifact.get("generated\_files", \[\])

    render\_note \= artifact.get("render\_note", "")

    if stage\_status \!= "completed":

        st.warning(f"程式碼轉譯Stage狀態：{stage\_status}，無法預覽檔案 / 產生套件")

        return

    \# 頂層資訊

    col1, col2 \= st.columns(\[1,1\])

    with col1:

        st.metric(label="產出檔案數", value=f"{len(generated\_files)}")

    with col2:

        st.text\_area("📝 轉譯備註", value=render\_note, height=80, disabled=True)

    st.divider()

    \# \========= 檔案選取下拉式清單 \=========

    file\_path\_list \= \[item\["file\_path"\] for item in generated\_files\]

    selected\_fp \= st.selectbox("選擇檔案預覽", options=file\_path\_list)

    \# 找到選取的檔案

    selected\_file \= next((f for f in generated\_files if f\["file\_path"\] \== selected\_fp), None)

    if selected\_file:

        file\_content \= selected\_file\["content"\]

        lang \= get\_code\_language(selected\_fp)

        char\_count \= len(file\_content)

        st.markdown(f"\*\*檔案路徑：\*\* \`{selected\_fp}\` ｜ 字元數：{char\_count:,}")

        \# 語法高亮程式碼區塊

        st.code(file\_content, language=lang, line\_numbers=True)

        \# 單檔下載按鈕

        st.download\_button(

            label="📥 下載此單一檔案",

            data=file\_content,

            file\_name=selected\_fp.split("/")\[-1\],

            mime="text/plain"

        )

    st.divider()

    \# \========= 完整套件 ZIP 下載 \=========

    zip\_buf \= package\_source\_zip(generated\_files)

    st.download\_button(

        label="📥 下載全部原始碼套件 ZIP",

        data=zip\_buf,

        file\_name="source\_package.zip",

        mime="application/zip",

        type="primary"

    )

## 使用方式

1. 將舊版 `render_code_renderer_panel` 整段替換成上面這一段  
2. 在Workflow Run詳細頁，維持原本呼叫：

render\_code\_renderer\_panel(run\_data)

## 功能清單

- ✅ 自動判斷副檔名，對應語法高亮（python/sql/yaml/json/bash/md/html…）  
- ✅ 行號顯示 `line_numbers=True`  
- ✅ 下拉選單切換各個產出檔案  
- ✅ 單獨下載當前檢視的檔案  
- ✅ 完整套件ZIP下載（保留原有功能）  
- ✅ 顯示檔案字數統計  
- ✅ 轉譯備註區塊  
- ✅ 狀態判斷，未完成Stage會提示，不能預覽

---

# 額外可選加強（可選擇要不要加上）

## 1\. 增加展開式全部檔案清單（全部檔案摺疊預覽）

在函數最後加上這一段：

with st.expander("📄 一次展開全部檔案預覽（大量檔案會比較慢）"):

    for f in generated\_files:

        fp \= f\["file\_path"\]

        content \= f\["content"\]

        lang \= get\_code\_language(fp)

        st.markdown(f"\#\#\# \`{fp}\`")

        st.code(content, language=lang, line\_numbers=True)

> ⚠️ 提醒：若一次產生幾十個檔案，這個展開區塊會耗費較多瀏覽器記憶體，適合小專案。

## 2\. 增加搜尋篩選檔案

在下拉選單前面加入檔案過濾：

search\_keyword \= st.text\_input("🔍 搜尋檔案名稱")

filtered\_files \= \[f for f in generated\_files if search\_keyword.lower() in f\["file\_path"\].lower()\]

file\_path\_list \= \[item\["file\_path"\] for item in filtered\_files\]

if not file\_path\_list:

    st.info("找不到符合關鍵字的檔案")

    return

# 測試檢查點

1. 執行完 skill\_code\_renderer，artifact 有 `generated_files`  
2. 下拉選單正常載入所有檔路徑  
3. .py 顯示python高亮、.sql顯示sql高亮  
4. 行號正常顯示  
5. 單檔下載、ZIP套件下載都正常  
6. 轉譯備註正確渲染

---

