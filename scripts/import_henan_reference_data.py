from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.infra.common import DATA_DIR
from modules.infra.sqlite_store import SqliteStore

SEED_DIR = PROJECT_ROOT / "data" / "seeds" / "henan"


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def import_henan_reference_data(db_path: Path) -> dict[str, int]:
    store = SqliteStore(db_path)
    try:
        sources = load_json(SEED_DIR / "sources.json")
        indicators = load_json(SEED_DIR / "agri_statistical_indicators.json")
        pesticides = load_json(SEED_DIR / "pesticide_catalog.json")

        for item in sources:
            store.upsert_data_source(item)

        for item in indicators:
            store.upsert_agri_statistical_indicator(item)

        for item in pesticides:
            store.upsert_pesticide_catalog_record(item)

        return {
            "sources": len(sources),
            "agri_statistical_indicators": len(indicators),
            "pesticide_catalog": len(pesticides),
        }
    finally:
        store.close()


def main() -> None:
    db_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    summary = import_henan_reference_data(db_path)
    print(f"Imported {summary['sources']} data sources into {db_path}")
    print(
        "Imported "
        f"{summary['agri_statistical_indicators']} agri_statistical_indicators into {db_path}"
    )
    print(f"Imported {summary['pesticide_catalog']} pesticide_catalog rows into {db_path}")


if __name__ == "__main__":
    main()
