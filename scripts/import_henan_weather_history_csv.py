from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.common import DATA_DIR
from modules.sqlite_store import SqliteStore


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, "", "NA", "N/A", "null", "NULL", "999999", "9999"):
        return None
    return float(value)


def _normalize_date(value: str) -> str:
    candidate = value.strip()
    if len(candidate) == 8 and candidate.isdigit():
        return f"{candidate[:4]}-{candidate[4:6]}-{candidate[6:8]}"
    if "-" in candidate:
        return candidate
    raise ValueError(f"Unsupported observation_date format: {value}")


def import_henan_weather_history_csv(
    csv_path: Path,
    db_path: Path,
    *,
    source_id: str = "cma_surf_cli_chn_mul_day_v3",
    province: str = "河南省",
    field_id: str | None = None,
) -> dict[str, int]:
    store = SqliteStore(db_path)
    imported_rows = 0
    imported_stations: set[str] = set()
    try:
        store.upsert_data_source(
            {
                "source_id": source_id,
                "source_name": "中国地面气候资料日值数据集（V3.0）",
                "publisher": "国家气象信息中心 / 中国气象数据网",
                "region_scope": "中国（可筛河南站点）",
                "source_type": "official_weather_dataset",
                "source_url": "https://m.data.cma.cn/data/detail/dataCode/SURF_CLI_CHN_MUL_DAY_V3.0.html",
                "access_level": "registered",
                "retrieval_date": "2026-04-15",
                "license": "",
                "notes": "Auto-registered by weather CSV importer.",
            }
        )
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                station_code = str(_first_value(row, "station_code", "站号", "区站号")).strip()
                station_name = str(_first_value(row, "station_name", "站名", "气象站")).strip()
                observation_date_raw = _first_value(
                    row,
                    "observation_date",
                    "日期",
                    "date",
                )
                if not station_code or not station_name or not observation_date_raw:
                    raise ValueError("CSV row missing station_code/station_name/observation_date")

                station_record = {
                    "station_code": station_code,
                    "station_name": station_name,
                    "province": str(_first_value(row, "province", "省份") or province),
                    "city": _first_value(row, "city", "城市", "市"),
                    "county": _first_value(row, "county", "区县", "县"),
                    "latitude": _to_float(_first_value(row, "latitude", "纬度")),
                    "longitude": _to_float(_first_value(row, "longitude", "经度")),
                    "elevation_m": _to_float(_first_value(row, "elevation_m", "海拔", "海拔高度")),
                    "source_id": source_id,
                    "notes": "Imported from CMA daily climate CSV",
                }
                store.upsert_weather_station(station_record)
                imported_stations.add(station_code)
                linked_field_id = field_id or store.find_nearest_field_id(
                    latitude=station_record["latitude"],
                    longitude=station_record["longitude"],
                    city=station_record["city"],
                    county=station_record["county"],
                )

                weather_record = {
                    "field_id": linked_field_id,
                    "station_code": station_code,
                    "station_name": station_name,
                    "observation_date": _normalize_date(str(observation_date_raw)),
                    "weather_summary": _first_value(row, "weather_summary", "天气概况", "天气现象"),
                    "temperature_avg_c": _to_float(_first_value(row, "temperature_avg_c", "平均气温", "TEM_Avg")),
                    "temperature_min_c": _to_float(_first_value(row, "temperature_min_c", "最低气温", "TEM_Min")),
                    "temperature_max_c": _to_float(_first_value(row, "temperature_max_c", "最高气温", "TEM_Max")),
                    "humidity_avg_percent": _to_float(
                        _first_value(row, "humidity_avg_percent", "平均相对湿度", "RHU_Avg")
                    ),
                    "precipitation_mm": _to_float(
                        _first_value(row, "precipitation_mm", "降水量", "PRE_Time_2020")
                    ),
                    "wind_speed_avg_mps": _to_float(
                        _first_value(row, "wind_speed_avg_mps", "平均风速", "WIN_S_2mi_Avg")
                    ),
                    "wind_direction": _first_value(row, "wind_direction", "风向", "WIN_D_S_Max"),
                    "sunshine_hours": _to_float(
                        _first_value(row, "sunshine_hours", "日照时数", "SSH")
                    ),
                    "source": source_id,
                    "raw_payload": row,
                }
                store.upsert_weather_history_daily(weather_record)
                imported_rows += 1
        return {
            "stations": len(imported_stations),
            "weather_history_daily": imported_rows,
        }
    finally:
        store.close()


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: PYTHONPATH=. .venv/bin/python scripts/import_henan_weather_history_csv.py <csv_path>",
            file=sys.stderr,
        )
        raise SystemExit(2)

    csv_path = Path(sys.argv[1]).resolve()
    db_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    summary = import_henan_weather_history_csv(csv_path, db_path)
    print(f"Imported {summary['stations']} weather stations into {db_path}")
    print(f"Imported {summary['weather_history_daily']} weather_history_daily rows into {db_path}")


if __name__ == "__main__":
    main()
