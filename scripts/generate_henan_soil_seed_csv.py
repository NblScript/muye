from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIELDS_CSV = PROJECT_ROOT / "data" / "seeds" / "henan" / "field_crop_seed" / "fields.csv"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "data" / "seeds" / "henan" / "soil_records.csv"


SOIL_PROFILES = {
    "潮土": {
        "ph": 6.8,
        "organic_matter_gkg": 18.2,
        "alkali_hydrolyzable_nitrogen_mgkg": 90.0,
        "available_phosphorus_mgkg": 24.0,
        "available_potassium_mgkg": 127.0,
        "moisture_percent": 22.0,
        "salinity_gkg": 0.8,
        "texture": "壤土",
    },
    "砂壤土": {
        "ph": 7.3,
        "organic_matter_gkg": 14.0,
        "alkali_hydrolyzable_nitrogen_mgkg": 78.0,
        "available_phosphorus_mgkg": 18.0,
        "available_potassium_mgkg": 116.0,
        "moisture_percent": 19.5,
        "salinity_gkg": 1.0,
        "texture": "砂壤土",
    },
    "黄褐土": {
        "ph": 6.6,
        "organic_matter_gkg": 16.5,
        "alkali_hydrolyzable_nitrogen_mgkg": 84.0,
        "available_phosphorus_mgkg": 21.0,
        "available_potassium_mgkg": 121.0,
        "moisture_percent": 23.0,
        "salinity_gkg": 0.9,
        "texture": "黏壤土",
    },
    "褐土": {
        "ph": 7.1,
        "organic_matter_gkg": 15.5,
        "alkali_hydrolyzable_nitrogen_mgkg": 82.0,
        "available_phosphorus_mgkg": 19.5,
        "available_potassium_mgkg": 118.0,
        "moisture_percent": 20.0,
        "salinity_gkg": 0.7,
        "texture": "壤土",
    },
    "黄棕壤": {
        "ph": 6.5,
        "organic_matter_gkg": 19.0,
        "alkali_hydrolyzable_nitrogen_mgkg": 95.0,
        "available_phosphorus_mgkg": 25.0,
        "available_potassium_mgkg": 131.0,
        "moisture_percent": 24.0,
        "salinity_gkg": 0.6,
        "texture": "壤土",
    },
}


def _load_fields(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def generate_soil_seed_csv(
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    *,
    fields_csv: Path = DEFAULT_FIELDS_CSV,
) -> Path:
    field_rows = _load_fields(fields_csv)
    rows: list[dict[str, object]] = []

    for index, field in enumerate(field_rows, start=1):
        soil_type = field.get("soil_type") or "潮土"
        profile = dict(SOIL_PROFILES.get(soil_type, SOIL_PROFILES["潮土"]))
        adjustment = round((index % 3) * 0.3, 1)
        rows.append(
            {
                "field_id": field["field_id"],
                "field_name": field["field_name"],
                "sample_date": f"2025-03-{17 + index:02d}",
                "depth_cm": 20,
                "ph": round(float(profile["ph"]) + (0.1 if index % 2 == 0 else 0.0), 1),
                "organic_matter_gkg": round(float(profile["organic_matter_gkg"]) + adjustment, 1),
                "alkali_hydrolyzable_nitrogen_mgkg": round(
                    float(profile["alkali_hydrolyzable_nitrogen_mgkg"]) + adjustment * 4,
                    1,
                ),
                "available_phosphorus_mgkg": round(
                    float(profile["available_phosphorus_mgkg"]) + adjustment * 2,
                    1,
                ),
                "available_potassium_mgkg": round(
                    float(profile["available_potassium_mgkg"]) + adjustment * 5,
                    1,
                ),
                "moisture_percent": round(float(profile["moisture_percent"]) + adjustment, 1),
                "salinity_gkg": round(float(profile["salinity_gkg"]) + (0.1 if index == 2 else 0.0), 1),
                "texture": profile["texture"],
                "source": "henan_soil_records_seed",
                "notes": "河南示例土壤检测 seed",
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def main() -> None:
    output_csv = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT_CSV
    generated = generate_soil_seed_csv(output_csv)
    print(f"Generated soil_records: {generated}")


if __name__ == "__main__":
    main()
