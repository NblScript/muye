from __future__ import annotations

import os

from main import MuyeApplication, _build_local_yolo_urls, _resolve_loopback_host


def test_resolve_loopback_host() -> None:
    assert _resolve_loopback_host("0.0.0.0") == "127.0.0.1"
    assert _resolve_loopback_host("::") == "127.0.0.1"
    assert _resolve_loopback_host("192.168.1.20") == "192.168.1.20"


def test_build_local_yolo_urls() -> None:
    detect_url, health_url = _build_local_yolo_urls("0.0.0.0", 8010)

    assert detect_url == "http://127.0.0.1:8010/detect"
    assert health_url == "http://127.0.0.1:8010/health"


def test_main_reads_qwen_mock_flag(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_USE_MOCK", "true")
    app = MuyeApplication()
    try:
        assert app.decision_engine.use_mock is True
    finally:
        import asyncio

        asyncio.run(app.shutdown())
    os.environ.pop("QWEN_USE_MOCK", None)
