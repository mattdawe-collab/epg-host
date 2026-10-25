"""Set up the nightly Telegram scorecard: saves the bot token and chat ID to .env and to the repo's GitHub secrets.

1. In Telegram, message @BotFather, send /newbot and follow the steps. It gives you a token like 123456:ABC-...
   Use a NEW bot just for the TV guide, not one another program already uses (HAL's bot, for example):
   finding your chat ID below reads the bot's messages, which would interrupt a program reading the same bot.
2. Run:  venv\\Scripts\\python tools\\set_telegram.py
3. Paste the token (right-click to paste - it is shown on screen and never printed back or logged).
4. Send your new bot any message when asked. The script finds your chat, sends a test message and saves both.

If you already know the chat ID, run with --chat-id <number> and the script never reads the bot's messages.
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from set_login import find_problems, update_env, update_github  # noqa: E402

API = "https://api.telegram.org/bot{token}/{method}"


def call(token, method, **params):
    try:
        response = requests.post(API.format(token=token, method=method), json=params, timeout=30)
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        sys.exit(f"Could not reach Telegram ({type(e).__name__}). Nothing was changed.")
    if not data.get("ok"):
        return None, data.get("description") or f"HTTP {response.status_code}"
    return data.get("result"), None


def find_chats(updates):
    """[(chat ID, who)] for the private chats in a getUpdates result, newest first, each once."""
    chats = {}
    for update in reversed(updates or []):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") == "private" and chat.get("id") is not None:
            who = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])) or chat.get("username") or "?"
            chats.setdefault(str(chat["id"]), who)
    return list(chats.items())


def ask_chat(token, bot_name):
    input(f"Now open Telegram, find @{bot_name}, send it any message (for example: hi), then press Enter here.")
    updates, problem = call(token, "getUpdates", timeout=0, limit=20)
    if problem:
        sys.exit(f"Telegram would not show the bot's messages ({problem}). If another program uses this bot, "
                 f"make a new bot, or run again with --chat-id. Nothing was changed.")
    chats = find_chats(updates)
    if not chats:
        sys.exit("No message found. Send the bot a message, then run this again. Nothing was changed.")
    chat_id, who = chats[0]
    if input(f"Send the scorecard to {who} (chat {chat_id})? [Y/n] ").strip().lower() not in ("", "y", "yes"):
        sys.exit("Nothing was changed.")
    return chat_id


def main(argv):
    token = input("Bot token from @BotFather: ").strip()
    problems = find_problems({"Bot token": token})
    if problems:
        sys.exit("; ".join(problems) + ". Nothing was changed.")
    me, problem = call(token, "getMe")
    if problem:
        sys.exit(f"Telegram refused this token ({problem}). Copy it again from @BotFather. Nothing was changed.")
    print(f"Token OK - bot @{me.get('username')}")
    chat_id = argv[argv.index("--chat-id") + 1].strip() if "--chat-id" in argv else ask_chat(token, me.get("username"))
    _, problem = call(token, "sendMessage", chat_id=chat_id,
                      text="TV guide scorecard is set up. You'll get one message after each nightly build.")
    if problem:
        sys.exit(f"Telegram would not deliver the test message ({problem}). Nothing was changed.")
    print("Test message sent - check Telegram.")
    secrets = {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}
    update_env(secrets)
    update_github(secrets)
    print("Done. The next nightly build sends the scorecard.")


if __name__ == "__main__":
    main(sys.argv[1:])
