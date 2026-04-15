from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "seeds" / "henan" / "field_crop_seed"


@dataclass(frozen=True)
class CitySeed:
    city_code: str
    city_name: str
    county_name: str
    center_lat: float
    center_lon: float
    soil_type: str


HENAN_CITY_SEEDS = [
    CitySeed("zz", "郑州", "中原区", 34.7473, 113.6249, "潮土"),
    CitySeed("kf", "开封", "龙亭区", 34.7970, 114.3076, "砂壤土"),
    CitySeed("xx", "新乡", "红旗区", 35.3030, 113.9268, "潮土"),
    CitySeed("zmd", "驻马店", "驿城区", 32.9802, 114.0284, "黄褐土"),
    CitySeed("ly", "洛阳", "洛龙区", 34.6197, 112.4540, "褐土"),
    CitySeed("ny", "南阳", "宛城区", 32.9907, 112.5283, "黄棕壤"),
]


def _build_square_geofence(latitude: float, longitude: float, area_mu: float) -> list[list[float]]:
    area_square_m = max(area_mu, 1.0) * 666.6667
    half_side_m = math.sqrt(area_square_m) / 2
    lat_delta = half_side_m / 111_000
    lon_delta = half_side_m / (111_000 * max(math.cos(math.radians(latitude)), 0.1))
    return [
        [round(longitude - lon_delta, 6), round(latitude - lat_delta, 6)],
        [round(longitude + lon_delta, 6), round(latitude - lat_delta, 6)],
        [round(longitude + lon_delta, 6), round(latitude + lat_delta, 6)],
        [round(longitude - lon_delta, 6), round(latitude + lat_delta, 6)],
    ]


def build_crop_rows() -> list[dict[str, object]]:
    return [
        {
            "crop_code": "winter_wheat",
            "crop_name": "冬小麦",
            "category": "grain",
            "variety": "河南主栽品系",
            "growth_cycle_days": 240,
            "water_demand_coefficient": 1.00,
            "typical_planting_month": "10",
            "typical_harvest_month": "06",
            "source": "generated_seed",
            "notes": "河南主粮作物，通常 10 月播种，次年 6 月收获。",
        },
        {
            "crop_code": "summer_corn",
            "crop_name": "夏玉米",
            "category": "grain",
            "variety": "河南夏播品系",
            "growth_cycle_days": 110,
            "water_demand_coefficient": 0.86,
            "typical_planting_month": "06",
            "typical_harvest_month": "09",
            "source": "generated_seed",
            "notes": "河南夏播作物，通常 6 月播种，9 月至 10 月收获。",
        },
    ]


def build_field_rows() -> list[dict[str, object]]:
    random.seed(20260415)
    rows: list[dict[str, object]] = []
    owner_ids = ["user_zheng", "user_agri_a", "user_agri_b"]

    for city_index, city in enumerate(HENAN_CITY_SEEDS, start=1):
        field_id = f"henan-{city.city_code}-{city_index:03d}"
        lat = round(city.center_lat + random.uniform(-0.08, 0.08), 6)
        lon = round(city.center_lon + random.uniform(-0.08, 0.08), 6)
        area_mu = round(random.uniform(35, 120), 2)
        rows.append(
            {
                "field_id": field_id,
                "field_code": f"HN-{city_index:03d}",
                "field_name": f"{city.city_name}示范田1号",
                "owner_user_id": owner_ids[(city_index - 1) % len(owner_ids)],
                "province": "河南省",
                "city": city.city_name,
                "county": city.county_name,
                "township": "",
                "village": "",
                "latitude": lat,
                "longitude": lon,
                "area_mu": area_mu,
                "area_hectare": round(area_mu * 0.0666667, 4),
                "geofence": json.dumps(_build_square_geofence(lat, lon, area_mu), ensure_ascii=False),
                "soil_type": city.soil_type,
                "irrigation_type": "喷灌",
                "source": "generated_seed",
                "notes": f"{city.city_name}农业基础样例地块",
            }
        )
    return rows


def build_crop_cycle_rows(field_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    reference_today = date.today()

    previous_corn_year = reference_today.year - 1
    corn_start = date(previous_corn_year, 6, 15)
    corn_harvest = date(previous_corn_year, 9, 28)

    wheat_start_year = reference_today.year - 1
    wheat_start = date(wheat_start_year, 10, 10)
    wheat_harvest = date(wheat_start_year + 1, 6, 5)
    wheat_status = "growing" if reference_today < wheat_harvest else "harvested"

    for field in field_rows:
        rows.append(
            {
                "field_id": str(field["field_id"]),
                "crop_code": "summer_corn",
                "year": corn_start.year,
                "season": "summer",
                "planting_date": corn_start.isoformat(),
                "harvest_date": corn_harvest.isoformat(),
                "area_mu": field["area_mu"],
                "expected_yield_kg": round(float(field["area_mu"]) * 42, 2),
                "actual_yield_kg": round(float(field["area_mu"]) * 40.5, 2),
                "status": "harvested",
                "source": "generated_seed",
                "notes": "过去一年内的夏玉米已完成收获。",
            }
        )
        rows.append(
            {
                "field_id": str(field["field_id"]),
                "crop_code": "winter_wheat",
                "year": wheat_start.year,
                "season": "winter",
                "planting_date": wheat_start.isoformat(),
                "harvest_date": wheat_harvest.isoformat(),
                "area_mu": field["area_mu"],
                "expected_yield_kg": round(float(field["area_mu"]) * 36, 2),
                "actual_yield_kg": None,
                "status": wheat_status,
                "source": "generated_seed",
                "notes": "当前生产季冬小麦记录。",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate_seed_csvs(output_dir: Path = OUTPUT_DIR) -> dict[str, Path]:
    crop_rows = build_crop_rows()
    field_rows = build_field_rows()
    crop_cycle_rows = build_crop_cycle_rows(field_rows)

    crop_path = output_dir / "crop_catalog.csv"
    field_path = output_dir / "fields.csv"
    cycle_path = output_dir / "field_crop_cycles.csv"

    write_csv(crop_path, crop_rows)
    write_csv(field_path, field_rows)
    write_csv(cycle_path, crop_cycle_rows)

    return {
        "crop_catalog": crop_path,
        "fields": field_path,
        "field_crop_cycles": cycle_path,
    }


def main() -> None:
    generated = generate_seed_csvs()
    for key, path in generated.items():
        print(f"Generated {key}: {path}")


if __name__ == "__main__":
    main()
