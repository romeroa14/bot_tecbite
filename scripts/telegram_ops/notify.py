from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, bot_token: str, chat_ids: list[str]):
        self.base = f"https://api.telegram.org/bot{bot_token}"
        self.chat_ids = chat_ids

    def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "HTML",
        disable_preview: bool = True,
    ) -> bool:
        targets = [chat_id] if chat_id else self.chat_ids
        ok = True
        for target in targets:
            try:
                resp = requests.post(
                    f"{self.base}/sendMessage",
                    json={
                        "chat_id": target,
                        "text": text[:4096],
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": disable_preview,
                    },
                    timeout=20,
                )
                data = resp.json()
                if not data.get("ok"):
                    log.warning("Telegram send failed chat=%s: %s", target, data)
                    ok = False
            except requests.RequestException as exc:
                log.exception("Telegram request error chat=%s: %s", target, exc)
                ok = False
        return ok

    def broadcast(self, text: str) -> bool:
        return self.send_message(text)


def escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
