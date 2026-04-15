from __future__ import annotations

import csv
import json

from scripts.generate_henan_field_crop_seed_csv import generate_seed_csvs


def test_generate_henan_field_crop_seed_csv_outputs_expected_files(tmp_path) -> None:
    generated = generate_seed_csvs(tmp_path)

    with generated["crop_catalog"].open("r", encoding="utf-8") as file:
        crop_rows = list(csv.DictReader(file))
    with generated["fields"].open("r", encoding="utf-8") as file:
        field_rows = list(csv.DictReader(file))
    with generated["field_crop_cycles"].open("r", encoding="utf-8") as file:
        cycle_rows = list(csv.DictReader(file))

    assert [row["crop_name"] for row in crop_rows] == ["冬小麦", "夏玉米"]
    assert len(field_rows) >= 5
    assert len(cycle_rows) == len(field_rows) * 2

    for field_row in field_rows:
        lat = float(field_row["latitude"])
        lon = float(field_row["longitude"])
        assert 31.0 <= lat <= 36.5
        assert 110.0 <= lon <= 116.5
        assert field_row["province"] == "河南省"
        assert field_row["city"]
        assert field_row["owner_user_id"]
        geofence = json.loads(field_row["geofence"])
        assert len(geofence) == 4

    statuses = {row["status"] for row in cycle_rows}
    assert statuses <= {"growing", "harvested"}
    crop_codes = {row["crop_code"] for row in cycle_rows}
    assert crop_codes == {"winter_wheat", "summer_corn"}
