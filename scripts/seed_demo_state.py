#!/usr/bin/env python
"""Seed a deterministic Muye demo task into SQLite and the event log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.demo_seed_service import seed_demo_state
from modules.infra.common import load_environment


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic demo workflow state")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not clear existing runtime tasks and demo events before seeding",
    )
    args = parser.parse_args()

    load_environment()
    result = seed_demo_state(clear_existing=not args.keep_existing)
    print(f"seeded request_id={result['request_id']} status={result['status']}")


if __name__ == "__main__":
    main()
