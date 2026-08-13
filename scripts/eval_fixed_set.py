from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.pipeline_planning_service import (  # noqa: E402
    attach_heatmap_trace,
    build_density_payload,
    plan_spray_mission,
)
from modules.drone.mission_planner import MissionPlanner, MissionPlannerError  # noqa: E402


DEFAULT_MANIFEST = ROOT_DIR / "data" / "eval" / "manifest.json"
REQUIRED_FIELDS = {
    "id",
    "image",
    "expected_pest",
    "crop",
    "weather_scenario",
    "expected_compliance",
}
REQUIRED_REGRESSION_FIELDS = {
    "image_sha256",
    "source_image_id",
    "source_class_id",
    "source_class_name",
    "annotation_provenance",
    "detections",
    "expected_regression",
}
VALID_COMPLIANCE = {"passed", "warning", "blocked"}
VALID_REGRESSION_STATUS = {"ok", "error"}
VALID_PLANNING_MODES = {"variable_rate", "uniform_fallback", "error"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IP102_IMAGE_PATTERN = re.compile(r"^IP(?P<class_index>\d{3})\d+\.[A-Za-z0-9]+$")

DEFAULT_FLIGHT_CONSTRAINTS = {
    "altitude_range_m": [2.0, 8.0],
    "speed_range_mps": [1.0, 6.0],
    "spray_rate_range_lpm": [0.3, 3.0],
    "max_safe_wind_speed_mps": 8.0,
}


class _EvalDroneController:
    """Small adapter that exercises the production planning selection path."""

    def __init__(self, flight_constraints: dict[str, Any]) -> None:
        self.planner = MissionPlanner(flight_constraints)

    def plan_spray_mission(
        self,
        *,
        field_context: dict[str, Any],
        current_weather: dict[str, Any],
    ) -> dict[str, Any]:
        return self.planner.plan_spray_mission(
            field_context=field_context,
            current_weather=current_weather,
        )


def _resolve_image(manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sha256(value: Any, *, label: str) -> str:
    normalized = str(value).strip().lower()
    if not SHA256_PATTERN.fullmatch(normalized):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return normalized


def _validate_regression_case(case: dict[str, Any]) -> None:
    case_id = case["id"]
    missing = sorted(REQUIRED_REGRESSION_FIELDS - set(case))
    if missing:
        raise ValueError(f"case {case_id} missing regression fields: {missing}")
    if not isinstance(case["detections"], list):
        raise ValueError(f"case {case_id} detections must be a list")
    if not str(case["annotation_provenance"]).strip():
        raise ValueError(f"case {case_id} annotation_provenance must not be empty")
    source_match = IP102_IMAGE_PATTERN.fullmatch(str(case["source_image_id"]))
    if source_match is None:
        raise ValueError(f"case {case_id} has invalid IP102 source_image_id")
    expected_class_id = int(source_match.group("class_index")) + 1
    if case["source_class_id"] != expected_class_id:
        raise ValueError(
            f"case {case_id} source_class_id must be {expected_class_id} "
            "for the zero-based IP102 filename prefix"
        )
    if not str(case["source_class_name"]).strip():
        raise ValueError(f"case {case_id} source_class_name must not be empty")

    expected = case["expected_regression"]
    if not isinstance(expected, dict):
        raise ValueError(f"case {case_id} expected_regression must be an object")
    if expected.get("status") not in VALID_REGRESSION_STATUS:
        raise ValueError(f"case {case_id} has invalid regression status")
    if expected.get("planning_mode") not in VALID_PLANNING_MODES:
        raise ValueError(f"case {case_id} has invalid planning_mode")
    _validate_sha256(
        expected.get("sha256"),
        label=f"case {case_id} expected_regression.sha256",
    )


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain non-empty cases")

    version = int(payload.get("version") or 1)
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"case {index} must be an object")
        missing = sorted(REQUIRED_FIELDS - set(case))
        if missing:
            raise ValueError(f"case {case.get('id', index)} missing fields: {missing}")
        case_id = str(case["id"]).strip()
        if not case_id:
            raise ValueError(f"case {index} id must not be empty")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)
        if case["expected_compliance"] not in VALID_COMPLIANCE:
            raise ValueError(f"case {case_id} has invalid expected_compliance")

        image_path = _resolve_image(path, str(case["image"]))
        if not image_path.exists():
            raise ValueError(f"case {case_id} missing image: {image_path}")

        normalized_case = dict(case)
        normalized_case["id"] = case_id
        normalized_case["image_path"] = str(image_path)
        if version >= 2:
            _validate_regression_case(normalized_case)
            expected_image_sha = _validate_sha256(
                normalized_case["image_sha256"],
                label=f"case {case_id} image_sha256",
            )
            actual_image_sha = _file_sha256(image_path)
            if actual_image_sha != expected_image_sha:
                raise ValueError(
                    f"case {case_id} image checksum mismatch: "
                    f"expected {expected_image_sha}, got {actual_image_sha}"
                )
            normalized_case["image_sha256"] = expected_image_sha
        normalized.append(normalized_case)

    result = dict(payload)
    result["version"] = version
    result["cases"] = normalized
    return result


def summarize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    cases = manifest["cases"]
    by_compliance = Counter(case["expected_compliance"] for case in cases)
    by_crop = Counter(case["crop"] for case in cases)
    by_weather = Counter(case["weather_scenario"] for case in cases)
    return {
        "total": len(cases),
        "by_compliance": dict(sorted(by_compliance.items())),
        "by_crop": dict(sorted(by_crop.items())),
        "by_weather": dict(sorted(by_weather.items())),
    }


def _merged_dict(base: Any, override: Any) -> dict[str, Any]:
    merged = dict(base) if isinstance(base, dict) else {}
    if isinstance(override, dict):
        merged.update(override)
    return merged


def _regression_inputs(
    manifest: dict[str, Any],
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    defaults = manifest.get("regression_defaults") or {}
    field_context = _merged_dict(
        defaults.get("field_context"),
        case.get("field_context"),
    )
    crop_cycle = _merged_dict(
        field_context.get("crop_cycle"),
        case.get("crop_cycle"),
    )
    crop_cycle["crop_name"] = str(
        case.get("crop_display_name") or crop_cycle.get("crop_name") or case["crop"]
    )
    field_context["crop_cycle"] = crop_cycle

    current_weather = _merged_dict(
        defaults.get("current_weather"),
        case.get("current_weather"),
    )
    flight_constraints = _merged_dict(
        DEFAULT_FLIGHT_CONSTRAINTS,
        defaults.get("flight_constraints"),
    )
    flight_constraints.update(case.get("flight_constraints") or {})
    return field_context, current_weather, flight_constraints


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_case(manifest: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Run one deterministic heatmap and spray-planning regression fixture."""
    field_context, current_weather, flight_constraints = _regression_inputs(
        manifest,
        case,
    )
    detections = case["detections"]
    density_grid, density_metadata = build_density_payload(
        field_context=field_context,
        detections=detections,
    )
    heatmap = {
        "metadata": density_metadata,
        "cells": density_grid,
    }

    try:
        controller = _EvalDroneController(flight_constraints)
        plan = plan_spray_mission(
            drone_controller=controller,
            field_context=field_context,
            current_weather=current_weather,
            detections=detections,
        )
        traced_plan = attach_heatmap_trace(
            plan,
            snapshot_id=f"fixed-eval:{case['id']}",
            density_metadata=density_metadata,
        )
        stable_payload = {
            "case_id": case["id"],
            "status": "ok",
            "heatmap": heatmap,
            "planning": {
                "source": traced_plan.get("source"),
                "planning_mode": traced_plan["planning_mode"],
                "heatmap_algorithm_version": traced_plan["heatmap_algorithm_version"],
                "degradation_reason": traced_plan.get("degradation_reason"),
                "base_rate_lpm": traced_plan.get("喷洒速率"),
                "spray_schedule": traced_plan.get("spray_schedule", []),
                "route": traced_plan.get("飞行路径", []),
                "spray_rate_policy": traced_plan["spray_rate_policy"],
            },
        }
    except (MissionPlannerError, TypeError, ValueError) as exc:
        stable_payload = {
            "case_id": case["id"],
            "status": "error",
            "heatmap": heatmap,
            "planning": {
                "planning_mode": "error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        }

    return {
        "case_id": case["id"],
        "sha256": _canonical_sha256(stable_payload),
        "payload": stable_payload,
    }


def _verify_result(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    expected = case["expected_regression"]
    payload = result["payload"]
    heatmap_metadata = payload["heatmap"]["metadata"]
    planning = payload["planning"]
    checks = {
        "sha256": result["sha256"],
        "status": payload["status"],
        "planning_mode": planning["planning_mode"],
        "accepted_detection_count": heatmap_metadata.get("accepted_detection_count"),
        "rejected_detection_count": heatmap_metadata.get("rejected_detection_count"),
    }
    failures: list[str] = []
    for key, actual in checks.items():
        if key in expected and expected[key] != actual:
            failures.append(
                f"{case['id']}.{key}: expected {expected[key]!r}, got {actual!r}"
            )
    return failures


def run_regression(manifest: dict[str, Any]) -> dict[str, Any]:
    if int(manifest.get("version") or 1) < 2:
        raise ValueError("regression execution requires manifest version 2 or newer")

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for case in manifest["cases"]:
        result = evaluate_case(manifest, case)
        case_failures = _verify_result(case, result)
        result["passed"] = not case_failures
        result["failures"] = case_failures
        results.append(result)
        failures.extend(case_failures)
    return {
        "passed": not failures,
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failures": failures,
        "results": results,
    }


def format_report(
    manifest: dict[str, Any],
    regression: dict[str, Any] | None = None,
) -> str:
    summary = summarize_manifest(manifest)
    lines = [
        "# Muye Fixed Eval Set",
        "",
        f"- Manifest version: {manifest.get('version', 1)}",
        f"- Total cases: {summary['total']}",
        f"- Compliance: {summary['by_compliance']}",
        f"- Crops: {summary['by_crop']}",
        f"- Weather: {summary['by_weather']}",
    ]
    if regression is not None:
        verdict = "PASS" if regression["passed"] else "FAIL"
        lines.extend([
            f"- Regression: {verdict} ({regression['passed_count']}/{regression['case_count']})",
            "",
            "| ID | Pest | Mode | Accepted/Rejected | SHA-256 | Result |",
            "|---|---|---|---:|---|---|",
        ])
        case_by_id = {case["id"]: case for case in manifest["cases"]}
        for result in regression["results"]:
            payload = result["payload"]
            metadata = payload["heatmap"]["metadata"]
            mode = payload["planning"]["planning_mode"]
            case = case_by_id[result["case_id"]]
            lines.append(
                "| {id} | {pest} | {mode} | {accepted}/{rejected} | `{sha}` | {verdict} |".format(
                    id=result["case_id"],
                    pest=case["expected_pest"],
                    mode=mode,
                    accepted=metadata.get("accepted_detection_count", 0),
                    rejected=metadata.get("rejected_detection_count", 0),
                    sha=result["sha256"],
                    verdict="PASS" if result["passed"] else "FAIL",
                )
            )
        if regression["failures"]:
            lines.extend(["", "## Failures", ""])
            lines.extend(f"- {failure}" for failure in regression["failures"])
    else:
        lines.extend([
            "",
            "| ID | Image | Pest | Crop | Weather | Compliance |",
            "|---|---|---|---|---|---|",
        ])
        for case in manifest["cases"]:
            lines.append(
                "| {id} | {image} | {expected_pest} | {crop} | {weather_scenario} | {expected_compliance} |".format(
                    **case
                )
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="验证牧野固定样例，并回归热力网格与变量喷洒输出",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, help="写入 Markdown 报告")
    parser.add_argument("--json-output", type=Path, help="写入机器可读 JSON 结果")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    regression = run_regression(manifest)
    report = format_report(manifest, regression)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(regression, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(report)
    return 0 if regression["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
