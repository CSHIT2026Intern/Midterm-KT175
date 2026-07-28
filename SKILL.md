---
name: azure-devops-report
description: Query Azure DevOps work items (title, state, last changed date) and produce a formatted or summarized report. Use when the user asks about their to-do list, all work items, or wants a summary of Azure DevOps tasks.
---

# Azure DevOps Report

## When to use this skill

Use this skill whenever the user asks things like:
- "我的待辦事項"、"我的 work item"、"my todo list"
- "所有的待辦事項"、"team 的待辦事項"、"all work items"
- "幫我摘要一下待辦事項"、"summarize my tasks"
- "我今天有什麼要做的"、"今天的任務"、"what do I need to do today"
- "有什麼要做的事情"、"接下來要做什麼"

## Required environment variables

These must be set before running the script:
- `AZDO_ORG` — Azure DevOps organization name
- `AZDO_PROJECT` — Azure DevOps project name
- `AZDO_PAT` — Personal Access Token with Work Items (Read) scope

Note: the whole skill shares ONE `AZDO_PAT`. That PAT's own `@Me` identity is
NOT the same as whoever is actually asking in Discord — do not use `@Me` in
any WIQL query. Instead, resolve the asker's own ADO identity first (see
"Identity resolution" below) and filter by that email explicitly.

## Identity resolution (do this BEFORE any "my" / personal query)

Whenever the user asks about **their own** work items ("我的待辦事項", "今天
要做什麼", etc. — anything personal, not "all"/"team"), first figure out
their Discord user ID from the message context, then look up whether they've
already linked an Azure DevOps identity:

```bash
python3 link_identity.py get <discord_user_id>
```

- If it prints `FOUND:<email>` → use that email as the assigned-identity
  filter in the next step. Do not ask the user anything, just proceed.
- If it prints `NOT_FOUND` → the user hasn't linked yet. Ask them for their
  Azure DevOps login email, e.g.:
  > ⚠️ 你還沒有綁定 Azure DevOps 帳號，麻煩告訴我你在 Azure DevOps 登入用的
  > Email，我幫你綁定，之後就不用再問了。

  Once they reply with an email, save it:
  ```bash
  python3 link_identity.py set <discord_user_id> <email_they_gave>
  ```
  Then proceed to query using that email.

Skip this whole identity-resolution step for "all" / "team" / "全部" style
queries — those aren't scoped to one person, so no identity lookup is
needed.

## Workflow

1. Determine query scope based on the user's request:
   - "my" / "個人" / "我的" / "今天" / personal phrasing → do identity
     resolution above, then query items assigned to that specific email
   - "all" / "全部" / "team" → query all work items in the project, no
     identity filter

2. Run the helper script using the `exec` tool:
   ```bash
   # Personal query (after identity resolution):
   python3 get_my_tasks.py --assigned "<the resolved email>"

   # All work items:
   python3 get_my_tasks.py
   ```
   This script queries Azure DevOps via WIQL (two-step: get IDs, then get
   details) and prints each work item's ID, title, state, and last changed
   date as plain text to stdout.

3. Parse the script's stdout output into a list of work items.

4. Reply as a Discord embed card via the `message` tool, not a plain-text
   bullet list. Build the embed like this:
   - `title`: context-appropriate, e.g. "📋 我的待辦事項" / "🌐 全部待辦事項"
   - `color` (decimal int), based on the highest priority present in the
     result set:
     - contains Priority 1 → `15548997` (red)
     - contains Priority 2 → `16426522` (orange)
     - otherwise → `2829617` (dark gray)
   - one embed `field` per State group:
     - `name`: `{state icon} {State} ({count} 項)`
       icons: New → 📝, Active/To Do → 🚀, Resolved → ✅, Closed → 🔒,
       otherwise → 📌
     - `value`: one line per item —
       `{priority icon} #{ID} [{Type}] {Title}\n └ 負責人：{AssignedTo} | 更新：{ChangedDate}`
       priority icons: 1 → 🔴, 2 → 🟠, 3 → 🟡, otherwise → ⚪
   - If the user asked for a summary ("摘要", "summarize") rather than a
     plain list, lead the embed `description` with a one-line count (total
     items, how many are high priority) before the per-state fields.

   Example `message` tool call:
   ```json
   {
     "action": "send",
     "channel": "discord",
     "to": "channel:<current channel id>",
     "message": "",
     "embeds": [
       {
         "title": "📋 我的待辦事項",
         "color": 2829617,
         "fields": [
           {
             "name": "🚀 To Do (1 項)",
             "value": "🟠 #7 [Task] TEST\n └ 負責人：陳佳君 | 更新：2026/7/23 下午 02:56",
             "inline": false
           }
         ]
       }
     ]
   }
   ```

5. Reply in Traditional Chinese unless the user wrote in English.

## Notes

- Do not print or log the value of `AZDO_PAT` anywhere in output.
- If the script errors with an authentication failure, tell the user their
  PAT may have expired and needs to be renewed in Azure DevOps, rather than
  retrying silently.
- Never use `@Me` in a WIQL query in this skill — it resolves to the shared
  PAT's own identity, not the Discord user asking.

## Discord 呈現格式（重要）

在 Discord 頻道回覆待辦事項清單或摘要時，一律使用 `message` 工具的
`embeds` 參數呈現成卡片，不要用純文字條列。

- 依 State 分組，每個 State 開一個 embed field
- field 名稱格式：`{狀態圖示} {State} ({數量} 項)`
  - New → 📝　Active/To Do → 🚀　Resolved → ✅　Closed → 🔒
- field 內容每筆格式：`{優先度圖示} #{ID} [{Type}] {Title}\n └ 負責人：{AssignedTo} | 更新：{ChangedDate}`
  - Priority 1 → 🔴　Priority 2 → 🟠　Priority 3 → 🟡　其他 → ⚪
- embed 顏色（color，十進位整數）依整批資料中最高優先度決定：
  - 有 Priority 1 → 15548997（紅）
  - 有 Priority 2 → 16426522（橘）
  - 其餘 → 2829617（深灰）
- embed 的 title 用查詢情境命名，例如「📋 我的待辦事項」「🌐 全部待辦事項」
- 呼叫範例：
  {
    "action": "send",
    "channel": "discord",
    "to": "channel:<目前頻道ID>",
    "message": "",
    "embeds": [{
      "title": "📋 我的待辦事項",
      "color": 2829617,
      "fields": [
        { "name": "📝 New (2 項)", "value": "🟠 #5 [Feature] OpenClaw\n └ 負責人：陳佳君 | 更新：2026/7/23 下午 02:52", "inline": false }
      ]
    }]
  }