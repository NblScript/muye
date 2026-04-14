#!/usr/bin/env python3
"""
SQLite migration helper to apply v1.1 constraints/indexes to existing databases.

- Ensures tasks.status has CHECK constraint (queued|running|completed|error)
- Ensures indexes on request_id for detections/weather_snapshots/decisions (created idempotently)

Usage:
  MUYE_DB_PATH=data/muye.db python -m scripts.migrate_to_v1_1
  # or
  python scripts/migrate_to_v1_1.py --db data/muye.db
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from modules.sqlite_store import SqliteStore


def run(db_path: Path) -> None:
    logger = logging.getLogger("muye.migration")
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logger.info("Applying v1.1 migration on %s", db_path)
    store = SqliteStore(db_path=db_path, logger=logger)
    store.close()
    logger.info("Migration finished for %s", db_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply SQLite migration to v1.1")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("MUYE_DB_PATH", "data/muye.db")),
        help="Path to the SQLite database (default from MUYE_DB_PATH or data/muye.db)",
    )
    args = parser.parse_args()
    run(args.db)
