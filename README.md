# OpenClaw × Discord × Azure DevOps

一個串接 **Discord**、**Azure DevOps**、**Azure OpenAI (gpt-5-mini)** 的 AI 個人助理，
讓團隊成員能直接在 Discord 上查詢 Azure DevOps 的待辦事項（work items），
並透過 AI 產生自然語言摘要與問答。

## 專案有兩條並行的實作路線

| | 獨立 Discord Bot | OpenClaw Agent 整合 |
|---|---|---|
| 技術基礎 | 純 `discord.py` 程式 | OpenClaw（本地 agent 框架）+ 自訂 skill |
| 互動方式 | Slash Command（`/todo`、`/summary` 等） | 頻道內 `@提及` + 自然語言 |
| 適合場景 | 固定、結構化的查詢流程 | 彈性口語提問，交給 AI 判斷意圖 |
| 目錄 | `discord_bot/` | `~/.openclaw/skills/azure-devops-report/` |

兩邊底層邏輯相通（同樣的 Azure DevOps WIQL 查詢方式、同樣的身份綁定機制），
可以並存使用，也可以之後擇一為主力。

---

## 一、技術架構

```
使用者 (Discord)
   │
   ├─ Slash Command ──▶ bot.py (discord.py) ──▶ Azure DevOps API（抓資料）
   │                                          └─▶ Azure OpenAI API（AI 摘要）
   │
   └─ @提及 + 自然語言 ──▶ OpenClaw Agent ──▶ azure-devops-report skill
                                            ├─▶ Azure DevOps API（抓資料）
                                            └─▶ Azure OpenAI (gpt-5-mini)（AI 回答）
```

三層分工：
- **Discord**：使用者輸入指令或自然語言、接收回覆的介面
- **Azure DevOps API**：資料來源，提供 work item 的標題、狀態、負責人、更新時間等
- **Azure OpenAI (gpt-5-mini)**：負責把原始資料整理成人看得懂的摘要或回答自由提問

---

## 二、獨立 Discord Bot（`discord_bot/`）

### 1. 建立 Application 與 Bot

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. **New Application** 建立新專案
3. 左側選單進入 **Bot** 頁面，點擊 **Reset Token** 取得 Bot Token
4. 開啟必要的 **Privileged Gateway Intents**：
   - `MESSAGE CONTENT INTENT`（讀取訊息內容需要）

### 2. 產生邀請連結（OAuth2 URL Generator）

- **Scopes**：勾選 `bot`、`applications.commands`（後者是 Slash Command 運作的必要條件）
- **Bot Permissions**：
  - 一般權限：檢視頻道
  - 文字頻道：傳送訊息、在討論串中傳送訊息、嵌入連結、讀取訊息歷史紀錄
  - 綜合權限：使用斜線指令

> 過程中曾誤勾選「管理者」權限，後續修正為僅勾選上述必要權限，降低風險。

產生網址後貼到瀏覽器開啟，選擇要加入的伺服器並授權。

### 3. 安裝依賴套件

```bash
pip install discord.py python-dotenv requests openai
```

### 4. 指令同步方式

初期使用全域同步（`tree.sync()`），發現同步後指令要等待最多 1 小時才會出現在
Discord 介面，測試效率太低。後續改為**伺服器限定同步**（需要 `DISCORD_GUILD_ID`），
改善為幾乎即時生效：

```python
guild = discord.Object(id=int(guild_id))
tree.copy_global_to(guild=guild)
synced = await tree.sync(guild=guild)
```

### 5. 指令總覽

| 指令 | 功能說明 |
|---|---|
| `/hello` | 測試 Bot 是否正常運作 |
| `/todo` | 查詢「指派給自己」的 work item，Embed 卡片呈現 |
| `/all` | 查詢**所有** work item，Embed 卡片呈現 |
| `/member <name>` | 查詢指定成員負責的待辦事項 |
| `/summary` | 查詢待辦事項後，透過 gpt-5-mini 產生摘要，Embed 卡片呈現 |
| `/link <ado_identity>` | 綁定自己的 Discord 帳號到 Azure DevOps Email |
| `@提及 + 問題` | 自然語言問答（例如「我有哪些高優先度的任務」），不需打 `/summary` |

### 6. 啟動

```bash
python bot.py
```

### 7. 定時推播功能

使用 `discord.ext.tasks` 的 `tasks.loop(time=...)`，設定每日固定時間（台北時區）
自動抓取所有 work item 並推播到指定頻道：

```python
TAIPEI_TZ = timezone(timedelta(hours=8))
PUSH_TIME = time(hour=8, minute=0, second=0, tzinfo=TAIPEI_TZ)
```

需在 `.env` 額外設定 `DISCORD_NOTIFY_CHANNEL_ID` 指定推播頻道。

---

## 三、OpenClaw Agent 整合

### 1. 為什麼要有這條路線

Mentor 指定專案要用 OpenClaw 框架運作，讓 Discord 上的互動可以交給通用 agent
處理（不限於固定指令，能理解口語化的問法），Azure DevOps 查詢能力則以
**skill**（`azure-devops-report`）的形式掛載進 agent。

### 2. 安裝 OpenClaw 本體

這一步是前面都沒提到、但其實是最先要做的：OpenClaw 是一個要另外安裝在機器上
（負責啟動的那台機器，例如你自己的電腦或一台 VPS）的 CLI 程式，跟 `discord_bot/`
裡純 Python 寫的 Bot 是兩回事，不會因為裝了 Python 套件就自動有。

**系統需求**：Node.js 22.22.3+ / 24.15+ / 25.9+（推薦 Node 24），macOS / Linux /
Windows 皆可。

**macOS / Linux / WSL2**：

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

**Windows（PowerShell）**：

```powershell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

安裝腳本會自動偵測作業系統、需要的話順便裝 Node、安裝 OpenClaw CLI，並跳出導覽
式的 onboarding 流程（會問你要串哪個 model、要啟用哪些 channel，可以先跳過，
之後再用下面「Model 串接」的步驟手動設定）。

**確認安裝成功**：

```bash
openclaw --version      # 確認 CLI 有裝起來
openclaw doctor         # 檢查設定有沒有問題（只看診斷，不要加 --fix，理由見下方坑點）
openclaw gateway status # 確認 Gateway 有在跑
```

如果 terminal 找不到 `openclaw` 指令，九成是 PATH 沒抓到 npm 的全域安裝目錄，
可以用 `npm prefix -g` 查全域套件裝在哪，再確認那個路徑有沒有在 `echo $PATH` 裡。

### 3. 連接 Discord 頻道

OpenClaw 本體也需要自己的 Discord Bot Token（可以跟 `discord_bot/` 那支獨立
程式共用同一個 Discord Application，也可以另外申請一個新的，避免兩邊搶著回覆
同一則訊息造成混亂）。

1. 到 [Discord Developer Portal](https://discord.com/developers/applications)
   建立 Application → Bot → Reset Token 拿到 Token
2. 一樣要開啟 **Message Content Intent**（Bot 頁面的 Privileged Gateway Intents）
3. 用 OAuth2 URL Generator 產生邀請連結，把 Bot 加進測試伺服器
4. 設定 Token 並啟用 Discord channel：

```bash
openclaw config set channels.discord.token "你的Discord Bot Token" --json
openclaw config set channels.discord.enabled true --json
openclaw gateway restart
```

5. 預設 DM 是走「配對（pairing）」流程，第一次私訊機器人時，需要用
   `openclaw pairing list discord` 查待審核的配對碼，再用
   `openclaw pairing approve discord <code>` 核准，之後才會回覆你。
6. 如果要在**群組頻道**（而不是 DM）裡用 `@提及` 呼叫機器人，預設
   `groupPolicy` 是 `allowlist`，需要在 config 裡明確把伺服器 ID / 頻道 ID
   加進允許清單，機器人才會在該頻道回話（否則就算 Token 正確，機器人也會
   安靜地忽略所有訊息，這是最常見的「明明設定了但沒反應」原因）。

設定完可以用 `openclaw channels status --probe` 檢查頻道連線狀態，確認沒問題
再繼續進行下面「Model 串接」的設定。

### 4. Model 串接：Azure OpenAI

**確認服務類型**：透過 mentor 提供的 API Key 與 endpoint 網址，比對網址內含
`openai.azure.com` 字樣，確認是 **Azure OpenAI Service**，而非 OpenAI 官方 API，
兩者串接方式不同：

- 需使用 `AzureOpenAI` 這個 client class（而非 `OpenAI`）
- 呼叫時使用的是 Azure 上設定的**部署名稱 (deployment name)**，而非 `gpt-5-mini` 字面字串
- 需額外提供 `azure_endpoint` 與 `api_version`

**OpenClaw config 設定重點**（`~/.openclaw/openclaw.json`）：

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "azure-gpt5mini": {
        "baseUrl": "https://<你的資源名稱>.openai.azure.com/openai/v1",
        "apiKey": "${AZURE_GPT5MINI_API_KEY}",
        "api": "openai-completions",
        "authHeader": false,
        "headers": { "api-key": "${AZURE_GPT5MINI_API_KEY}" },
        "models": [
          {
            "id": "gpt-5-mini",
            "name": "GPT-5 Mini (Azure)",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 200000,
            "maxTokens": 16384,
            "compat": { "supportsStore": false }
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "models": {
        "azure-gpt5mini/gpt-5-mini": { "alias": "GPT" }
      },
      "model": { "primary": "azure-gpt5mini/gpt-5-mini" }
    }
  }
}
```

**⚠️ 重要坑點**：`openclaw doctor --fix` 會自動把不在 OpenClaw 內建目錄裡的
model id「升級」成它認為的官方版本（例如把自訂的 `gpt-5-mini` 改成
`gpt-5.4-mini`），這會直接蓋掉 Azure 對應設定。**只用 `openclaw gateway restart`
重啟，避免對這份 config 跑 `doctor --fix`。**

`env` 檔案（`~/.openclaw/env`）需要：

```
AZURE_GPT5MINI_API_KEY=你的Azure金鑰
```

### 5. `azure-devops-report` skill

放在 `~/.openclaw/skills/azure-devops-report/`，包含：

| 檔案 | 功能 |
|---|---|
| `SKILL.md` | 定義觸發語句、查詢流程、身份綁定邏輯、Discord embed 排版規則 |
| `get_my_tasks.py` | 實際打 Azure DevOps WIQL API 抓資料，支援 `--assigned <email>` 篩選 |
| `link_identity.py` | 查詢／寫入 Discord 使用者 ↔ ADO Email 對照表 |
| `member_links.json` | 對照表資料（跟獨立 bot 共用同一份格式） |

環境變數（`~/.openclaw/env`）：

```
AZDO_ORG=CSH2026ITIntern
AZDO_PROJECT=2026-OpenClaw
AZDO_PAT=你的PAT
```

### 6. 身份綁定機制（重要）

整個 skill 共用**同一組 `AZDO_PAT`**，WIQL 裡的 `@Me` 永遠對應到「PAT 擁有者
本人」，不會是在 Discord 上發問的那個人。因此：

- 查「我的」待辦事項前，agent 會先用 `link_identity.py get <discord_user_id>`
  查對照表
- 沒綁定過 → 引導使用者提供 ADO Email，再用 `link_identity.py set` 寫入
- 綁定過 → 直接用該 Email 作為 `AssignedTo` 篩選條件查詢，不再用 `@Me`

`member_links.json` 也可以直接手動編輯，不一定要透過對話綁定：

```json
{
  "Discord使用者ID": "對應的ADO Email"
}
```

### 7. Discord 呈現：Embed 卡片

Agent 透過內建 `message` 工具的 `embeds` 參數送出卡片式排版（依狀態分組、
依優先度變色），規則細節寫在 `SKILL.md` 裡，不需要另外啟用 OpenClaw 的
`discord` skill（那個是進階訊息管理操作用的，如編輯、reaction、poll）。

### 8. 啟動 / 重啟

```bash
openclaw doctor          # 只看診斷，不加 --fix
openclaw gateway restart
openclaw skills list     # 確認 azure-devops-report 是 ✓ ready
```

---

## 四、Azure DevOps API 串接（兩邊共用邏輯）

### 1. 認證設定

- 使用 **Personal Access Token (PAT)**：Azure DevOps → User settings → Personal Access Tokens
- 權限 Scope：至少勾選 `Work Items → Read`
- 使用 Basic Auth 呼叫 API（帳號留空，密碼放 PAT）

### 2. 兩段式查詢邏輯

Azure DevOps REST API 設計上分兩步：

1. **`get_work_item_ids()`**：用 **WIQL**（類似 SQL 的查詢語言）查詢，取得符合條件的
   work item **ID 清單**
   ```
   POST /_apis/wit/wiql
   ```
2. **`get_work_item_details()`**：用取得的 ID 清單查詢完整內容（標題、狀態、負責人、
   最後更新時間等）
   ```
   GET /_apis/wit/workitems?ids=...
   ```

### 3. 查詢範圍演進

- 初期：`WHERE [System.AssignedTo] = @Me`（只查 PAT 擁有者自己的待辦，後來發現
  這在多人共用同一組 PAT 的情境下是錯的）
- 中期：擴充為查詢**全部 work item**，加入 `System.ChangedDate` 欄位
- 目前：支援指定 `AssignedTo = <特定 email>`，搭配身份綁定機制，讓每個 Discord
  使用者查到自己的待辦

### 4. 開發過程中的問題排除

| 問題 | 原因 | 解法 |
|---|---|---|
| `TF200016: 專案不存在` | 網址中專案名稱誤帶入 `{}` 符號 | 修正網址格式，移除範本符號 |
| 查詢結果為空陣列 | Work item 尚未指派給該帳號 | 改查全部 work item 或手動指派測試 |
| `JSONDecodeError` | Azure DevOps 回傳非 JSON 內容（PAT 過期或無效） | 加入除錯用 print 檢查回應狀態碼與內容，確認並更新 PAT |
| `@Me` 查到別人的資料 | 多人共用同一組 PAT，`@Me` 只會對應 PAT 擁有者 | 改用 email 明確篩選 + 身份綁定對照表 |

---

## 五、Azure OpenAI 摘要 / 問答邏輯

`llm_client.py` 提供兩支函式：

- **`summarize_work_items(items)`**：固定格式摘要
  1. 把 work item 資料整理成純文字清單
  2. 組成 prompt，要求 AI 依規則輸出：開頭總結任務數量與高優先度項目、依狀態分類、
     條列式排版、依任務屬性加上對應 Emoji
- **`answer_work_item_question(items, question)`**：自由問答
  - 不套固定排版格式，直接根據使用者的問題原句回答，回答方式由問題本身決定
  - 只根據原始資料回答，資料中沒有的內容不編造

---

## 六、環境變數總表

**`discord_bot/.env`**

```
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
DISCORD_NOTIFY_CHANNEL_ID=

AZDO_ORG=
AZDO_PROJECT=
AZDO_PAT=

AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

**`~/.openclaw/env`**

```
AZURE_GPT5MINI_API_KEY=
AZDO_ORG=
AZDO_PROJECT=
AZDO_PAT=
```

> 補充：OpenClaw 這條路線的 Discord Bot Token **不是**放在 `~/.openclaw/env`
> 裡，而是用 `openclaw config set channels.discord.token "..." --json` 寫進
> `~/.openclaw/openclaw.json`（細節見「三、2. 安裝 OpenClaw 本體」與「三、3.
> 連接 Discord 頻道」）。跟獨立 Bot 那邊 `.env` 裡的 `DISCORD_BOT_TOKEN` 是
> 兩組完全獨立的設定，可以用同一個 Discord Application 的 Token，也可以
> 各自申請不同的 Bot，避免兩邊搶著回同一則訊息。

---

## 七、專案檔案結構

```
discord_bot/
├── bot.py                 # Discord Bot 主程式，所有指令、自然語言問答、定時任務入口
├── get_my_tasks.py        # Azure DevOps API 串接（抓資料邏輯）
├── formatter.py           # 待辦事項排版邏輯（獨立於抓資料邏輯，避免多人協作衝突）
├── llm_client.py          # Azure OpenAI 串接、摘要與自然語言問答邏輯
├── member_links.json      # Discord 帳號 ↔ Azure DevOps Email 對照表
├── .env                   # 環境變數（不納入版控）
└── .env.example           # .env 範本

~/.openclaw/skills/azure-devops-report/
├── SKILL.md                # OpenClaw agent 用的技能定義：觸發語句、流程、排版規則
├── get_my_tasks.py         # 同上，支援 --assigned 參數
├── link_identity.py        # 身份綁定查詢／寫入小工具
└── member_links.json       # 對照表（可與 discord_bot/ 那份共用或同步）
```

**分檔案的原因**：初期抓資料與排版邏輯放在同一支檔案，多人協作時容易互相覆蓋
修改內容，因此拆分成獨立模組，讓不同工作項目（抓資料 / 排版 / AI 邏輯）可以
並行開發，降低衝突風險。

---

## 八、分工

| 成員 | 負責檔案 | 負責內容 |
|---|---|---|
| 陳佳君（我） | `bot.py`（骨架）、`get_my_tasks.py`（初版）、`llm_client.py`（初版） | 打地基：Discord Bot 建置、Azure DevOps API 串接、Azure OpenAI 初版串接；後續協調並合併組員修改內容；OpenClaw agent 串接與 skill 開發 |
| 蔡易均 | `bot.py`（新增指令與排程）、`get_my_tasks.py`（擴充） | 新增 `/all` 指令、查詢範圍擴充為全部 work item、每日定時推播功能 |
| 陳冠瑋 | `llm_client.py`（優化）、`bot.py`（`/summary` 呈現） | 調整 AI 摘要 prompt（結構化排版、狀態分類、Emoji 規則）、將 `/summary` 改為 Discord Embed 卡片呈現 |

---

## 九、開發過程中的協作問題與解法

開發中期，兩位組員同時修改 `bot.py`（一位新增 `/all` 指令與排程功能，另一位將
`/summary` 改為 Embed 卡片呈現），因未同步基準版本，導致出現兩份不相容的檔案。
後續透過人工比對兩份修改內容，合併為單一版本，並記錄以下經驗：

- 多人協作修改同一檔案前，應先同步告知避免版本分歧
- 之後可考慮採用 Git 版本控制搭配分支管理，降低類似衝突發生機率

OpenClaw 串接過程中另外踩過的坑：

- `openclaw doctor --fix` 會自動「升級」不在內建目錄裡的自訂 model id，多次
  蓋掉 Azure 對應設定，改為只用 `openclaw gateway restart` 重啟
- 自訂 provider 的 `apiVersion` 欄位在當前版本尚未支援，改用 Azure 統一
  `/openai/v1` 端點繞過需要手動指定 api-version 的限制
- 內建 `openai` provider 覆蓋 `baseUrl` 指向 Azure 有已知社群 bug（回報
  "model does not exist"），改用自訂 provider 名稱較穩定

---

## 十、目前狀態

- ✅ Discord Bot（獨立版）建置完成，可正常收發指令
- ✅ Azure DevOps API 串接完成，可查詢個人 / 全部 work item
- ✅ Azure OpenAI (gpt-5-mini) 摘要功能完成，並以 Embed 卡片呈現
- ✅ 每日定時推播功能完成
- ✅ 自然語言問答功能完成（`@提及 + 問題`，不限於固定摘要格式）
- ✅ OpenClaw agent 串接 Azure OpenAI (gpt-5-mini) 完成
- ✅ `azure-devops-report` skill 開發完成，可在 OpenClaw 內查詢待辦事項
- ✅ OpenClaw 端身份綁定機制完成（解決多人共用 PAT、`@Me` 查錯人的問題）
- ✅ OpenClaw 端 Discord Embed 卡片呈現規則完成
- 🔲 待優化：`discord_bot/` 與 OpenClaw skill 的 `member_links.json` 目前分開維護，
  規劃改為共用同一份檔案或建立同步機制
- 🔲 待優化：支援更彈性的日期範圍查詢（例如「這週還有哪些沒做完」）
- 🔲 待評估：兩條實作路線（獨立 bot vs. OpenClaw agent）是否收斂為單一主力方案
# discordBot
