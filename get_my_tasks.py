"""
Azure DevOps 資料抓取模組（組員 A 負責）
------------------------------------------
只負責「跟 Azure DevOps 要資料」，不負責排版。
排版邏輯在 formatter.py 裡（組員 B 負責），兩個檔案分開改，避免衝突。

之後要做新指令、擴充查詢範圍時：
複製 get_work_item_ids() 和 get_work_item_details()，改 WIQL 查詢條件就好。
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()  # 讀取同資料夾下的 .env 檔案，確保不管誰匯入這支檔案都會先載入

# ------------------------------------------------------------------
# 設定區：這些放進 .env，不要直接寫死在程式碼裡（尤其是 PAT）
# ------------------------------------------------------------------
ORG = os.environ.get("AZDO_ORG", "CSH2026ITIntern")
PROJECT = os.environ.get("AZDO_PROJECT", "2026-OpenClaw")
PAT = os.environ.get("AZDO_PAT")  # 存取權杖，不要 commit 進 git

if not PAT:
    raise RuntimeError(
        "找不到 PAT，請先設定環境變數 AZDO_PAT\n"
        "例如：export AZDO_PAT='你的PAT字串'"
    )

AUTH = HTTPBasicAuth("", PAT)
API_VERSION = "7.1"


def get_work_item_ids(wiql_query: str) -> list[int]:
    """
    第一步：用 WIQL 查詢，只會拿到符合條件的 work item ID 清單。
    """
    url = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/wiql"
    params = {"api-version": API_VERSION}
    body = {"query": wiql_query}

    resp = requests.post(url, params=params, json=body, auth=AUTH)
    resp.raise_for_status()

    data = resp.json()
    ids = [item["id"] for item in data.get("workItems", [])]
    return ids


def get_work_item_details(ids: list[int]) -> list[dict]:
    """
    第二步：拿到 ID 之後，查詳細內容（標題、狀態、最後更新日期等）。
    回傳的每一筆資料格式（給組員 B 參考，寫 formatter.py 時要用到）：

    {
        "id": 2,
        "fields": {
            "System.Title": "...",
            "System.State": "...",
            "System.WorkItemType": "...",
            "System.ChangedDate": "2026-07-23T05:38:34.317Z",
            "System.AssignedTo": {"displayName": "..."},
            ...
        }
    }
    """
    if not ids:
        return []

    url = f"https://dev.azure.com/{ORG}/_apis/wit/workitems"
    params = {
        "ids": ",".join(str(i) for i in ids),
        "api-version": API_VERSION,
    }

    resp = requests.get(url, params=params, auth=AUTH)
    resp.raise_for_status()

    data = resp.json()
    return data.get("value", [])


def build_query(assigned_identity: str | None = None) -> str:
    """
    組出 WIQL 查詢字串。

    - assigned_identity 有給值：查「指派給這個 ADO 身分（email）」的項目
      注意：不用 @Me，因為整支程式共用同一組 AZDO_PAT，@Me 永遠只會對應到
      PAT 擁有者本人，不會是實際在 Discord 上發問的那個人。
      正確做法是由呼叫端（skill / bot）先把 Discord 帳號換成本人的 ADO
      email，再傳進來這裡當作篩選條件。
    - assigned_identity 是 None：查全部 work items，不篩選負責人。
    """
    base = (
        "SELECT [System.Id], [System.Title], [System.State], [System.ChangedDate] "
        "FROM WorkItems "
        "WHERE [System.State] <> 'Removed'"
    )
    if assigned_identity:
        safe_identity = assigned_identity.replace("'", "''")
        base += f" AND [System.AssignedTo] = '{safe_identity}'"
    base += " ORDER BY [System.Id] ASC"
    return base


if __name__ == "__main__":
    import sys

    # 用法：
    #   python get_my_tasks.py                    -> 查全部 work items
    #   python get_my_tasks.py --assigned <email>  -> 查指定 ADO 身分名下的 work items
    assigned_identity = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--assigned":
        assigned_identity = sys.argv[2]

    query = build_query(assigned_identity)

    ids = get_work_item_ids(query)
    print(f"找到 {len(ids)} 筆 work item，ID: {ids}")

    details = get_work_item_details(ids)
    for item in details:
        print(item["id"], item["fields"].get("System.Title"))
