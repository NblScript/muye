#!/usr/bin/env python3
"""Exercise the running smoke containers through their public HTTP boundaries."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]


class SmokeCheckError(RuntimeError):
    """Raised when a container smoke contract is not met."""


def request_bytes(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> tuple[int, bytes, str]:
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeCheckError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeCheckError(f"{method} {url} failed: {exc.reason}") from exc


def request_json(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    _, raw, _ = request_bytes(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout=timeout,
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeCheckError(f"{url} did not return JSON") from exc
    if not isinstance(payload, dict):
        raise SmokeCheckError(f"{url} returned {type(payload).__name__}, expected object")
    return payload


def encode_multipart(
    *,
    field_name: str,
    file_path: Path,
    fields: dict[str, str] | None = None,
) -> tuple[bytes, str]:
    boundary = f"----muye-smoke-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in (fields or {}).items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {media_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _assert_live(payload: dict[str, Any], label: str) -> None:
    if payload.get("status") != "ok":
        raise SmokeCheckError(f"{label} liveness failed: {payload}")


def _assert_fake_detection(payload: dict[str, Any]) -> None:
    results = payload.get("results") or []
    detections = results[0].get("detections", []) if results else []
    if not any(item.get("pest_type") == "aphid" for item in detections):
        raise SmokeCheckError(f"fake YOLO did not return the aphid fixture: {payload}")


def _task_has_uploaded_detection(state: dict[str, Any], filename: str) -> bool:
    latest = state.get("latest_task") or {}
    if Path(str(latest.get("image_path") or "")).name != filename:
        return False
    detections = latest.get("detections") or []
    return any(item.get("pest_type") == "aphid" for item in detections)


def _validate_real_detections(state: dict[str, Any], filename: str) -> dict[str, int] | None:
    latest = state.get("latest_task") or {}
    if Path(str(latest.get("image_path") or "")).name != filename:
        return None
    if latest.get("status") == "failed":
        raise SmokeCheckError(
            f"real-model task failed: {latest.get('message') or 'unknown pipeline error'}"
        )

    detections = latest.get("detections") or []
    if not detections:
        return None

    counts: dict[str, int] = {}
    for detection in detections:
        pest_type = str(detection.get("pest_type") or "").strip()
        confidence = detection.get("confidence")
        position = detection.get("position") or {}
        if not pest_type:
            raise SmokeCheckError(f"real YOLO returned a detection without pest_type: {detection}")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise SmokeCheckError(f"real YOLO returned invalid confidence: {detection}")
        if position.get("coordinate_space") != "image_pixel":
            raise SmokeCheckError(f"real YOLO detection is not in image_pixel space: {detection}")
        dimensions = [position.get(name) for name in ("image_width", "image_height")]
        if not all(isinstance(value, (int, float)) and float(value) > 0 for value in dimensions):
            raise SmokeCheckError(f"real YOLO detection is missing image dimensions: {detection}")
        counts[pest_type] = counts.get(pest_type, 0) + 1
    return counts


def run_smoke(
    *,
    backend_url: str,
    frontend_url: str,
    yolo_url: str,
    sample_path: Path,
    pipeline_timeout: float,
) -> None:
    if not sample_path.is_file():
        raise SmokeCheckError(f"sample image not found: {sample_path}")

    _assert_live(request_json(f"{backend_url}/live"), "backend")
    backend_health = request_json(f"{backend_url}/health")
    pipeline_health = (backend_health.get("checks") or {}).get("pipeline_runtime") or {}
    if backend_health.get("status") != "ok" or pipeline_health.get("ready") is not True:
        raise SmokeCheckError(f"backend pipeline is not ready: {backend_health}")
    _, frontend_html, content_type = request_bytes(f"{frontend_url}/")
    if "html" not in content_type or b"<html" not in frontend_html.lower():
        raise SmokeCheckError("frontend root did not return the application HTML")
    _assert_live(request_json(f"{frontend_url}/api/live"), "frontend proxy")

    yolo_health = request_json(f"{yolo_url}/health")
    if yolo_health.get("mode") != "smoke_fake" or yolo_health.get("is_simulated") is not True:
        raise SmokeCheckError(f"YOLO service is not explicitly simulated: {yolo_health}")

    yolo_body, yolo_content_type = encode_multipart(
        field_name="images",
        file_path=sample_path,
        fields={"confidence_threshold": "0.25"},
    )
    detection_payload = request_json(
        f"{yolo_url}/detect",
        method="POST",
        body=yolo_body,
        headers={"Content-Type": yolo_content_type},
    )
    _assert_fake_detection(detection_payload)

    upload_body, upload_content_type = encode_multipart(
        field_name="file",
        file_path=sample_path,
    )
    upload = request_json(
        f"{frontend_url}/api/demo/upload-image",
        method="POST",
        body=upload_body,
        headers={"Content-Type": upload_content_type},
    )
    uploaded_filename = str(upload.get("filename") or "")
    if not uploaded_filename:
        raise SmokeCheckError(f"upload response is missing filename: {upload}")

    deadline = time.monotonic() + pipeline_timeout
    last_state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last_state = request_json(f"{frontend_url}/api/workflow/state")
        if _task_has_uploaded_detection(last_state, uploaded_filename):
            print(
                "container smoke passed: frontend -> backend -> watchdog -> fake YOLO -> workflow",
                flush=True,
            )
            return
        time.sleep(1)
    raise SmokeCheckError(
        f"pipeline did not publish the uploaded aphid detection within {pipeline_timeout:.0f}s; "
        f"last state={json.dumps(last_state, ensure_ascii=False)[:1200]}"
    )


def run_real_model_smoke(
    *,
    backend_url: str,
    frontend_url: str,
    sample_path: Path,
    pipeline_timeout: float,
) -> None:
    if not sample_path.is_file():
        raise SmokeCheckError(f"sample image not found: {sample_path}")

    _assert_live(request_json(f"{backend_url}/live"), "backend")
    backend_health = request_json(f"{backend_url}/health")
    checks = backend_health.get("checks") or {}
    pipeline_health = checks.get("pipeline_runtime") or {}
    model_health = checks.get("yolo_model") or {}
    if backend_health.get("status") != "ok" or pipeline_health.get("ready") is not True:
        raise SmokeCheckError(f"backend pipeline is not ready: {backend_health}")
    if model_health.get("status") != "ok" or model_health.get("model_exists") is not True:
        raise SmokeCheckError(f"real YOLO model is not available: {model_health}")
    if model_health.get("mode") == "smoke_fake" or model_health.get("is_simulated") is True:
        raise SmokeCheckError(f"real-model smoke reached a simulated YOLO service: {model_health}")

    _, frontend_html, content_type = request_bytes(f"{frontend_url}/")
    if "html" not in content_type or b"<html" not in frontend_html.lower():
        raise SmokeCheckError("frontend root did not return the application HTML")
    _assert_live(request_json(f"{frontend_url}/api/live"), "frontend proxy")

    upload_body, upload_content_type = encode_multipart(
        field_name="file",
        file_path=sample_path,
    )
    upload = request_json(
        f"{frontend_url}/api/demo/upload-image",
        method="POST",
        body=upload_body,
        headers={"Content-Type": upload_content_type},
    )
    uploaded_filename = str(upload.get("filename") or "")
    if not uploaded_filename:
        raise SmokeCheckError(f"upload response is missing filename: {upload}")

    deadline = time.monotonic() + pipeline_timeout
    last_state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last_state = request_json(f"{frontend_url}/api/workflow/state")
        counts = _validate_real_detections(last_state, uploaded_filename)
        if counts:
            print(
                "real-model container smoke passed: "
                f"frontend -> backend -> watchdog -> real YOLO -> workflow; detections={counts}",
                flush=True,
            )
            return
        time.sleep(1)
    raise SmokeCheckError(
        f"real YOLO did not publish a detection for {sample_path.name} within "
        f"{pipeline_timeout:.0f}s; last state="
        f"{json.dumps(last_state, ensure_ascii=False)[:1200]}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "real"), default="fake")
    parser.add_argument("--backend-url", default="http://127.0.0.1:18080")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5174")
    parser.add_argument("--yolo-url", default="http://127.0.0.1:18010")
    parser.add_argument(
        "--sample",
        type=Path,
        default=ROOT_DIR / "data" / "samples" / "aphids_01.jpg",
    )
    parser.add_argument("--pipeline-timeout", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.mode == "real":
            run_real_model_smoke(
                backend_url=args.backend_url.rstrip("/"),
                frontend_url=args.frontend_url.rstrip("/"),
                sample_path=args.sample,
                pipeline_timeout=args.pipeline_timeout,
            )
        else:
            run_smoke(
                backend_url=args.backend_url.rstrip("/"),
                frontend_url=args.frontend_url.rstrip("/"),
                yolo_url=args.yolo_url.rstrip("/"),
                sample_path=args.sample,
                pipeline_timeout=args.pipeline_timeout,
            )
    except SmokeCheckError as exc:
        print(f"container smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
