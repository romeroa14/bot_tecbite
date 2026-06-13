from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from .config import Settings
from . import db
from .formatters import (
    format_active,
    format_client,
    format_handoffs,
    format_push,
    format_search_results,
    format_stats,
    format_today,
    help_text,
)
from .notify import TelegramClient

log = logging.getLogger(__name__)

SQL_STATS = """
WITH state_daily AS (
    SELECT
        COUNT(*) FILTER (WHERE slots_complete = TRUE) AS complete_slots,
        COUNT(*) FILTER (WHERE stage = 'recommend') AS recommend_count
    FROM instagram_conversation_state
    WHERE updated_at >= NOW() - INTERVAL '1 day'
),
event_metrics AS (
    SELECT
        COUNT(*) FILTER (
            WHERE event_type = 'recommendation'
              AND COALESCE(payload->>'source_ref', '') = ''
        )::numeric AS recommendations_without_source,
        COUNT(*) FILTER (WHERE event_type = 'recommendation')::numeric AS recommendation_events,
        percentile_cont(0.95) WITHIN GROUP (
            ORDER BY NULLIF(payload->>'technical_latency_ms', '')::double precision
        ) AS technical_latency_p95_ms
    FROM instagram_conversation_event
    WHERE created_at >= NOW() - INTERVAL '1 day'
)
SELECT
    ROUND(CASE WHEN s.recommend_count = 0 THEN 0
         ELSE (s.complete_slots::numeric / s.recommend_count) * 100 END, 2) AS slots_completion_percent,
    ROUND(CASE WHEN e.recommendation_events = 0 THEN 0
         ELSE (e.recommendations_without_source / e.recommendation_events) * 100 END, 2) AS technical_without_source_percent,
    0::numeric AS compatibility_precision_percent,
    ROUND(COALESCE(e.technical_latency_p95_ms, 0)::numeric, 2) AS technical_latency_p95_ms
FROM state_daily s
CROSS JOIN event_metrics e
"""


class OpsBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tg = TelegramClient(settings.bot_token, settings.chat_ids)
        self.offset = 0

    def authorized(self, user_id: int | None) -> bool:
        if user_id is None:
            return False
        if not self.settings.allowed_user_ids:
            return True
        return str(user_id) in self.settings.allowed_user_ids

    def handle_update(self, update: dict) -> None:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        chat_id = str(msg["chat"]["id"])
        user = msg.get("from") or {}
        user_id = user.get("id")

        if chat_id not in self.settings.chat_ids and str(chat_id) not in self.settings.chat_ids:
            log.info("Ignoring chat %s (not in TELEGRAM_OPS_CHAT_IDS)", chat_id)
            return

        text = str(msg.get("text") or "").strip()
        if not text.startswith("/"):
            return

        if not self.authorized(user_id):
            self.tg.send_message(
                "⛔ No tienes permiso para usar comandos ops.",
                chat_id=chat_id,
            )
            return

        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        reply = self.dispatch(cmd, arg.strip())
        self.tg.send_message(reply, chat_id=chat_id)

    def dispatch(self, cmd: str, arg: str) -> str:
        conn = db.connect(self.settings.db_dsn)
        try:
            if cmd in ("/start", "/help"):
                return help_text()
            if cmd == "/hoy":
                row = db.fetch_one(conn, db.SQL_TODAY_SUMMARY) or {}
                return format_today(row)
            if cmd == "/activos":
                rows = db.fetch_all(conn, db.SQL_ACTIVE)
                return format_active(rows)
            if cmd == "/handoffs":
                rows = db.fetch_all(conn, """
                    SELECT conversation_id, make, model, year, category, stage, updated_at
                    FROM instagram_conversation_state
                    WHERE stage = 'handoff'
                      AND updated_at >= NOW() - INTERVAL '48 hours'
                    ORDER BY updated_at DESC LIMIT 10
                """)
                return format_handoffs(rows)
            if cmd == "/stats":
                row = db.fetch_one(conn, SQL_STATS) or {}
                return format_stats(row)
            if cmd == "/cliente":
                if not arg:
                    return "Uso: /cliente \\<conversation_id\\> o /cliente Toyota Corolla"
                return self._client_lookup(conn, arg)
            return "Comando no reconocido. Usa /help"
        finally:
            conn.close()

    def _client_lookup(self, conn, arg: str) -> str:
        if re.match(r"^[\w-]{6,}$", arg) and " " not in arg:
            row = db.fetch_one(conn, db.SQL_CLIENT, (arg, arg))
            return format_client(row)

        tokens = arg.split()
        if len(tokens) >= 2:
            make, model = tokens[0], " ".join(tokens[1:])
            rows = db.fetch_all(
                conn,
                db.SQL_SEARCH_CLIENTS,
                (f"%{arg}%", f"%{arg}%", make, f"%{model}%"),
            )
            if len(rows) == 1:
                row = db.fetch_one(conn, db.SQL_CLIENT, (rows[0]["conversation_id"], rows[0]["conversation_id"]))
                return format_client(row)
            return format_search_results(rows)

        rows = db.fetch_all(conn, db.SQL_SEARCH_CLIENTS, (f"%{arg}%", f"%{arg}%", "", ""))
        if len(rows) == 1:
            row = db.fetch_one(conn, db.SQL_CLIENT, (rows[0]["conversation_id"], rows[0]["conversation_id"]))
            return format_client(row)
        return format_search_results(rows)

    def poll_forever(self) -> None:
        log.info("Ops bot polling started (chats=%s)", self.settings.chat_ids)
        while True:
            try:
                import requests

                resp = requests.get(
                    f"{self.tg.base}/getUpdates",
                    params={"timeout": self.settings.poll_timeout, "offset": self.offset},
                    timeout=self.settings.poll_timeout + 10,
                )
                data = resp.json()
                if not data.get("ok"):
                    log.warning("getUpdates failed: %s", data)
                    time.sleep(5)
                    continue
                for update in data.get("result", []):
                    self.offset = update["update_id"] + 1
                    try:
                        self.handle_update(update)
                    except Exception:
                        log.exception("handle_update failed")
            except Exception:
                log.exception("poll loop error")
                time.sleep(5)


def push_notification(settings: Settings, notify_type: str, payload: dict) -> bool:
    conn = db.connect(settings.db_dsn)
    try:
        cid = str(payload.get("conversation_id", ""))
        mid = str(payload.get("message_id", ""))
        if not db.try_log_notification(conn, cid, mid, notify_type, payload):
            return False
        text = format_push(notify_type, payload)
        return TelegramClient(settings.bot_token, settings.chat_ids).broadcast(text)
    finally:
        conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass
    settings = Settings.from_env()
    bot = OpsBot(settings)
    bot.tg.broadcast(
        "✅ <b>Tecbite Ops Bot</b> en línea.\n\n"
        "El equipo de mercadeo puede usar /help para ver comandos.\n"
        "Las alertas de Instagram DM llegarán aquí automáticamente."
    )
    bot.poll_forever()


if __name__ == "__main__":
    main()
