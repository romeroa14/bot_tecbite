from __future__ import annotations

import os
from dataclasses import dataclass


def _split_ids(raw: str) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    chat_ids: list[str]
    allowed_user_ids: list[str]
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_pass: str
    poll_timeout: int

    @classmethod
    def from_env(cls) -> Settings:
        token = os.getenv("TELEGRAM_OPS_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_OPS_BOT_TOKEN is required")

        chat_ids = _split_ids(os.getenv("TELEGRAM_OPS_CHAT_IDS", ""))
        if not chat_ids:
            raise RuntimeError("TELEGRAM_OPS_CHAT_IDS is required (group or user chat id)")

        allowed = _split_ids(os.getenv("TELEGRAM_OPS_ALLOWED_USER_IDS", ""))
        return cls(
            bot_token=token,
            chat_ids=chat_ids,
            allowed_user_ids=allowed,
            db_host=os.getenv("DB_HOST", "n8n.yavingos.com"),
            db_port=int(os.getenv("DB_PORT", "5433")),
            db_name=os.getenv("DB_NAME", "n8ntecbite_db"),
            db_user=os.getenv("DB_USER", "postgres"),
            db_pass=os.getenv("DB_PASS", ""),
            poll_timeout=int(os.getenv("TELEGRAM_OPS_POLL_TIMEOUT", "25")),
        )

    @property
    def db_dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_pass}"
        )
