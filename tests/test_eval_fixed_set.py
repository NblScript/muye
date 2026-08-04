from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.eval_fixed_set import (
    DEFAULT_MANIFEST,
    evaluate_case,
    load_manifest,
    run_regression,
    summarize_manifest,
)


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


def test_fixed_heatmap_regression_manifest_is_deterministic() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)

    first = run_regression(manifest)
    second = run_regression(manifest)

    assert first["passed"] is True
    assert first["case_count"] == 6
    assert first["passed_count"] == 6
    assert [item["sha256"] for item in first["results"]] == [
        item["sha256"] for item in second["results"]
    ]


def test_fixed_heatmap_regression_covers_pests_and_degradation_modes() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    regression = run_regression(manifest)

    pests = {case["expected_pest"] for case in manifest["cases"]}
    modes = {
        result["payload"]["planning"]["planning_mode"]
        for result in regression["results"]
    }

    assert {"aphid", "brown_planthopper", "rice_leaf_roller"} <= pests
    assert modes == {"variable_rate", "uniform_fallback", "error"}

    invalid_case = next(
        case for case in manifest["cases"] if case["id"] == "invalid-geofence-blocked"
    )
    invalid_result = evaluate_case(manifest, invalid_case)
    assert invalid_result["payload"]["status"] == "error"
    assert invalid_result["payload"]["heatmap"]["metadata"]["reason"] == "invalid_geofence"


def test_fixed_heatmap_regression_reports_baseline_drift() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    changed = copy.deepcopy(manifest)
    changed["cases"][0]["expected_regression"]["sha256"] = "0" * 64

    regression = run_regression(changed)

    assert regression["passed"] is False
    assert regression["passed_count"] == 5
    assert regression["failures"][0].startswith("aphid-variable-rate.sha256")


def test_version_two_manifest_rejects_changed_image(tmp_path: Path) -> None:
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"fixed-image")
    manifest = {
        "version": 2,
        "cases": [
            {
                "id": "checksum",
                "image": str(image),
                "image_sha256": hashlib.sha256(b"different-image").hexdigest(),
                "source_image_id": "IP024000016.jpg",
                "source_class_id": 25,
                "source_class_name": "aphids",
                "expected_pest": "aphid",
                "crop": "wheat",
                "weather_scenario": "normal",
                "expected_compliance": "passed",
                "annotation_provenance": "test_fixture",
                "detections": [],
                "expected_regression": {
                    "status": "ok",
                    "planning_mode": "uniform_fallback",
                    "sha256": "0" * 64,
                },
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="image checksum mismatch"):
        load_manifest(path)


def test_version_two_manifest_rejects_ip102_off_by_one_class_id(tmp_path: Path) -> None:
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"fixed-image")
    manifest = {
        "version": 2,
        "cases": [
            {
                "id": "off-by-one",
                "image": str(image),
                "image_sha256": hashlib.sha256(b"fixed-image").hexdigest(),
                "source_image_id": "IP024000016.jpg",
                "source_class_id": 24,
                "source_class_name": "aphids",
                "expected_pest": "aphid",
                "crop": "wheat",
                "weather_scenario": "normal",
                "expected_compliance": "passed",
                "annotation_provenance": "test_fixture",
                "detections": [],
                "expected_regression": {
                    "status": "ok",
                    "planning_mode": "uniform_fallback",
                    "sha256": "0" * 64,
                },
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="zero-based IP102 filename prefix"):
        load_manifest(path)
