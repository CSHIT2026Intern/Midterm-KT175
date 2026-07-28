"""
身份綁定小工具（給 azure-devops-report skill 用）
------------------------------------------------
跟 bot.py 用的是同一份 member_links.json 格式：
  { "<discord_user_id>": "<ado email>", ... }

這樣不管是走 OpenClaw agent（這支腳本）還是獨立的 bot.py，
綁定過一次的人在兩邊都認得，不用分別綁兩次。

用法（給 agent 透過 exec 呼叫）：
  查詢是否已綁定：
      python link_identity.py get <discord_user_id>
      -> 有綁定：印出 FOUND:<email>
      -> 沒綁定：印出 NOT_FOUND

  新增/更新綁定：
      python link_identity.py set <discord_user_id> <ado_email>
      -> 成功印出 OK
"""

import json
import sys
from pathlib import Path

LINKS_PATH = Path(__file__).parent / "member_links.json"


def _load() -> dict:
    if not LINKS_PATH.exists():
        return {}
    try:
        with open(LINKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(links: dict) -> None:
    with open(LINKS_PATH, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python link_identity.py get|set <discord_user_id> [ado_email]")
        sys.exit(1)

    action = sys.argv[1]
    discord_user_id = sys.argv[2]
    links = _load()

    if action == "get":
        identity = links.get(discord_user_id)
        if identity:
            print(f"FOUND:{identity}")
        else:
            print("NOT_FOUND")
        return

    if action == "set":
        if len(sys.argv) < 4:
            print("用法: python link_identity.py set <discord_user_id> <ado_email>")
            sys.exit(1)
        ado_email = sys.argv[3]
        links[discord_user_id] = ado_email
        _save(links)
        print("OK")
        return

    print(f"未知的 action: {action}（只支援 get / set）")
    sys.exit(1)


if __name__ == "__main__":
    main()
