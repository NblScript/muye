from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval_fixed_set import load_manifest, summarize_manifest


def test_eval_manifest_requires_existing_images(tmp_path: Path) -> None:
    manifest = {
        "version": 1,
        "cases": [
            {
                "id": "missing",
                "image": "missing.jpg",
                "expected_pest": "aphid",
                "crop": "wheat",
                "weather_scenario": "normal",
                "expected_compliance": "passed",
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="missing image"):
        load_manifest(path)


def test_eval_manifest_summary_counts_cases_by_compliance(tmp_path: Path) -> None:
    image = tmp_path / "aphids.jpg"
    image.write_bytes(b"fake")
    manifest = {
        "version": 1,
        "cases": [
            {
                "id": "aphid-normal",
                "image": str(image),
                "expected_pest": "aphid",
                "crop": "wheat",
                "weather_scenario": "normal",
                "expected_compliance": "passed",
            },
            {
                "id": "wind-high",
                "image": str(image),
                "expected_pest": "brown_planthopper",
                "crop": "rice",
                "weather_scenario": "wind_high",
                "expected_compliance": "warning",
            },
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = load_manifest(path)
    summary = summarize_manifest(loaded)

    assert summary["total"] == 2
    assert summary["by_compliance"] == {"passed": 1, "warning": 1}
    assert summary["by_crop"] == {"rice": 1, "wheat": 1}
