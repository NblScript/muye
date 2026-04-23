from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.infra.common import DATA_DIR
from modules.infra.sqlite_store import SqliteStore


DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "seeds" / "henan" / "soil_records.csv"


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, "", "NA", "N/A", "null", "NULL"):
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if value in (None, "", "NA", "N/A", "null", "NULL"):
        return None
    return int(float(value))


def _resolve_field_id(store: SqliteStore, row: dict[str, Any]) -> str:
    field_id = _first_value(row, "field_id", "地块ID", "地块Id")
    if field_id:
        return str(field_id)

    field_name = _first_value(row, "field_name", "地块名称")
    if not field_name:
        raise ValueError("CSV row missing field_id/field_name")

    matched = store.fetch_one(
        """
        SELECT field_id
        FROM fields
        WHERE field_name = ?
        ORDER BY field_id ASC
        LIMIT 1
        """,
        (str(field_name),),
    )
    if matched is None:
        raise ValueError(f"Unable to resolve field_id for soil row: {field_name}")
    return str(matched["field_id"])


def import_henan_soil_records_csv(
    csv_path: Path,
    db_path: Path,
    *,
    source_id: str = "henan_soil_records_seed",
) -> dict[str, int]:
    store = SqliteStore(db_path)
    imported_rows = 0
    try:
        store.upsert_data_source(
            {
                "source_id": source_id,
                "source_name": "河南土壤检测示例 seed",
                "publisher": "muye",
                "region_scope": "河南省",
                "source_type": "generated_seed",
                "source_url": "local://data/seeds/henan/soil_records.csv",
                "access_level": "local",
                "retrieval_date": "2026-04-16",
                "license": "",
                "notes": "Auto-registered by soil records importer.",
            }
        )
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                field_id = _resolve_field_id(store, row)
                record = {
                    "field_id": field_id,
                    "sample_date": _first_value(row, "sample_date", "采样日期"),
                    "depth_cm": _to_int(_first_value(row, "depth_cm", "采样深度(cm)", "采样深度")),
                    "ph": _to_float(_first_value(row, "ph", "pH")),
                    "organic_matter_gkg": _to_float(
                        _first_value(row, "organic_matter_gkg", "有机质(g/kg)", "有机质")
                    ),
                    "alkali_hydrolyzable_nitrogen_mgkg": _to_float(
                        _first_value(
                            row,
                            "alkali_hydrolyzable_nitrogen_mgkg",
                            "碱解氮(mg/kg)",
                            "碱解氮",
                        )
                    ),
                    "available_phosphorus_mgkg": _to_float(
                        _first_value(row, "available_phosphorus_mgkg", "有效磷(mg/kg)", "有效磷")
                    ),
                    "available_potassium_mgkg": _to_float(
                        _first_value(row, "available_potassium_mgkg", "速效钾(mg/kg)", "速效钾")
                    ),
                    "moisture_percent": _to_float(
                        _first_value(row, "moisture_percent", "含水率(%)", "含水率")
                    ),
                    "salinity_gkg": _to_float(_first_value(row, "salinity_gkg", "盐分(g/kg)", "盐分")),
                    "texture": _first_value(row, "texture", "土壤质地"),
                    "source": _first_value(row, "source") or source_id,
                    "raw_payload": row,
                }
                store.upsert_soil_record(record)
                imported_rows += 1
        return {"soil_records": imported_rows}
    finally:
        store.close()


def main() -> None:
    csv_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_CSV_PATH
    db_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    summary = import_henan_soil_records_csv(csv_path, db_path)
    print(f"Imported {summary['soil_records']} soil_records rows into {db_path}")


if __name__ == "__main__":
    main()
