#!/usr/bin/env python3
"""CLI: send a test notification to configured Telegram ops chats."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from telegram_ops.bot import push_notification
from telegram_ops.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Telegram ops test notification")
    parser.add_argument("--type", default="lead_ready", choices=[
        "lead_ready", "handoff", "new_vehicle", "category_switch",
    ])
    parser.add_argument("--payload", default="{}", help="JSON payload")
    args = parser.parse_args()
    settings = Settings.from_env()
    payload = json.loads(args.payload)
    ok = push_notification(settings, args.type, payload)
    print("sent" if ok else "skipped_or_failed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
