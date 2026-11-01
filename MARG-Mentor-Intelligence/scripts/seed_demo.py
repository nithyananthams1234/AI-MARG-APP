"""Load DEMO DATA into the engine database (development only).

Existing demo rows are replaced; engine records (executions, proposals, plans) are kept.
Dates are relative to the next working day on or after today (Asia/Kolkata by default).

Usage:  uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.config import ConfigurationError, DbBackend, get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.seed.demo_data import demo_anchor_date, seed_demo_data  # noqa: E402
from app.utils.datetime_utils import local_date, utcnow  # noqa: E402


async def main() -> int:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(f"CONFIGURATION ERROR: {exc}")
        return 2
    db = Database.from_settings(settings)
    try:
        info = await db.verify()  # guard: refuses forbidden databases / wrong schema
        print(f"Target verified: {info['database']} / schema {info['schema']}")
        if settings.db_backend is DbBackend.sqlite:
            await db.create_all()
        else:
            async with db.engine.connect() as conn:
                tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            if "alembic_version" not in tables:
                print("Tables not found. Run migrations first:  uv run alembic upgrade head")
                return 1
        anchor = demo_anchor_date(local_date(utcnow(), settings.tz))
        counts = await seed_demo_data(db, anchor)
    finally:
        await db.dispose()
    print(f"DEMO DATA loaded (anchor date {anchor.isoformat()}):")
    for table, count in counts.items():
        print(f"  {table:20s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
