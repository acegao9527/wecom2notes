#!/usr/bin/env python3
"""批量导入消息并进入统一投递链。"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.importers.batch import load_messages
from src.services.database import DatabaseService, init_db
from src.services.message_processor import process_message


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="CSV、Markdown、HTML 或文本文件路径")
    parser.add_argument("--source", default="import")
    args = parser.parse_args()

    load_dotenv()
    init_db(os.getenv("SQLITE_DB_PATH", "data/wecom2notes.db"))
    DatabaseService.run_migrations()
    for msg in load_messages(args.path, source=args.source):
        await process_message(msg)


if __name__ == "__main__":
    asyncio.run(main())
