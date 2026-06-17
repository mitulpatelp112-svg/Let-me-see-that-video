"""A dependency-free Telegram bot.

Uses long polling against the Telegram Bot API with nothing but the standard
library. Share a video link to the bot from your phone and it absorbs it
automatically — no command required.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .absorber import absorb, find_urls
from .config import Config
from .library import Library

_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramClient:
    def __init__(self, token: str, timeout: int = 50):
        self.token = token
        self.timeout = timeout

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        url = _API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(params).encode("utf-8")
        # Network timeout is the long-poll timeout plus a margin.
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=self.timeout + 15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": self.timeout}
        if offset is not None:
            params["offset"] = offset
        result = self._call("getUpdates", params)
        return result.get("result", []) if result.get("ok") else []

    def send_message(self, chat_id: int, text: str) -> None:
        try:
            self._call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": text[:4096],
                    "disable_web_page_preview": True,
                },
            )
        except urllib.error.URLError:
            pass


def _offset_path(library: Library) -> Path:
    return library.root / ".telegram_offset"


def _read_offset(library: Library) -> int | None:
    path = _offset_path(library)
    if path.is_file():
        try:
            return int(path.read_text().strip())
        except ValueError:
            return None
    return None


def _write_offset(library: Library, offset: int) -> None:
    _offset_path(library).write_text(str(offset), encoding="utf-8")


def _summary(record: dict[str, Any]) -> str:
    bits = [f"✅ Absorbed: {record.get('title')}"]
    if record.get("uploader"):
        bits.append(f"by {record['uploader']}")
    bits.append(f"[{record.get('platform')}]")
    line = " ".join(bits)
    src = record.get("transcript_source")
    if src:
        line += f"\n📝 transcript captured ({src})"
    else:
        line += "\n📝 no transcript available"
    return line


def handle_message(
    message: dict[str, Any],
    config: Config,
    library: Library,
    reply: Callable[[int, str], None],
    *,
    absorb_fn: Callable[..., dict[str, Any]] = absorb,
) -> None:
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    user_id = (message.get("from") or {}).get("id")
    if chat_id is None:
        return

    if config.allowed_user_ids and user_id not in config.allowed_user_ids:
        reply(chat_id, "Sorry, you are not authorised to use this bot.")
        return

    text = message.get("text") or message.get("caption") or ""
    if text.strip() in {"/start", "/help"}:
        reply(
            chat_id,
            "Send me a link from YouTube, TikTok, Instagram, etc. and I'll "
            "absorb it into your library automatically.\nYour Telegram user id "
            f"is: {user_id}",
        )
        return

    urls = find_urls(text)
    if not urls:
        reply(chat_id, "I didn't find a link in that message. Send me a video URL.")
        return

    for url in urls:
        try:
            record = absorb_fn(url, config, library)
            prefix = "Already in your library — " if record.get("already_absorbed") else ""
            reply(chat_id, prefix + _summary(record))
        except Exception as exc:  # noqa: BLE001
            reply(chat_id, f"⚠️ Couldn't absorb {url}\n{type(exc).__name__}: {exc}")


def run_bot(config: Config) -> None:
    if not config.telegram_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot with @BotFather and put "
            "the token in your .env file."
        )
    library = Library(config.library_dir)
    client = TelegramClient(config.telegram_token, timeout=config.poll_timeout)
    offset = _read_offset(library)
    print(f"Bot running. Library: {library.root}. Send it a link from your phone.")

    while True:
        try:
            updates = client.get_updates(offset)
        except urllib.error.URLError as exc:
            print(f"Network error while polling: {exc}. Retrying in 5s.")
            time.sleep(5)
            continue
        except KeyboardInterrupt:
            print("\nStopping bot.")
            return

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("channel_post")
            if message:
                handle_message(message, config, library, client.send_message)
            _write_offset(library, offset)
