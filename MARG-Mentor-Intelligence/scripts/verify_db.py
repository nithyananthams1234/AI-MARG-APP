"""Verify the engine database target (guard + connectivity). Prints no secrets.

Usage:  uv run python scripts/verify_db.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ConfigurationError, get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402


async def main() -> int:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(f"CONFIGURATION ERROR: {exc}")
        return 2
    db = Database.from_settings(settings)
    try:
        info = await db.verify()
    except Exception as exc:
        print(f"DATABASE CHECK FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        await db.dispose()
    print("Database target verified:")
    for key, value in info.items():
        print(f"  {key:9s}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
