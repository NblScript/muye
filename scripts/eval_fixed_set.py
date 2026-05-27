from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT_DIR / "data" / "eval" / "manifest.json"
REQUIRED_FIELDS = {
    "id",
    "image",
    "expected_pest",
    "crop",
    "weather_scenario",
    "expected_compliance",
}
VALID_COMPLIANCE = {"passed", "warning", "blocked"}


def _resolve_image(manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain non-empty cases")

    normalized: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"case {index} must be an object")
        missing = sorted(REQUIRED_FIELDS - set(case))
        if missing:
            raise ValueError(f"case {case.get('id', index)} missing fields: {missing}")
        if case["expected_compliance"] not in VALID_COMPLIANCE:
            raise ValueError(f"case {case['id']} has invalid expected_compliance")
        image_path = _resolve_image(path, str(case["image"]))
        if not image_path.exists():
            raise ValueError(f"case {case['id']} missing image: {image_path}")
        normalized_case = dict(case)
        normalized_case["image_path"] = str(image_path)
        normalized.append(normalized_case)

    result = dict(payload)
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


def format_report(manifest: dict[str, Any]) -> str:
    summary = summarize_manifest(manifest)
    lines = [
        "# Muye Fixed Eval Set",
        "",
        f"- Total cases: {summary['total']}",
        f"- Compliance: {summary['by_compliance']}",
        f"- Crops: {summary['by_crop']}",
        f"- Weather: {summary['by_weather']}",
        "",
        "| ID | Image | Pest | Crop | Weather | Compliance |",
        "|---|---|---|---|---|---|",
    ]
    for case in manifest["cases"]:
        lines.append(
            "| {id} | {image} | {expected_pest} | {crop} | {weather_scenario} | {expected_compliance} |".format(
                **case
            )
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="验证并汇总牧野固定样例评测集")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, help="写入 Markdown 报告")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    report = format_report(manifest)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
