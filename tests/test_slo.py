"""Tests for SLO metrics collector."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.slo import SLOMetrics


def test_initial_snapshot_all_ok():
    m = SLOMetrics()
    snap = m.snapshot()
    assert snap["api"]["success_rate"] == 1.0
    assert snap["api"]["ok"] is True
    assert snap["pipeline"]["completion_rate"] == 1.0
    assert snap["pipeline"]["ok"] is True
    assert snap["websocket"]["stability"] == 1.0
    assert snap["websocket"]["ok"] is True
    assert snap["availability"]["ok"] is True


def test_api_success_rate_counts_5xx():
    m = SLOMetrics()
    for _ in range(95):
        m.record_request(200)
    for _ in range(5):
        m.record_request(500)
    snap = m.snapshot()
    assert snap["api"]["total_60s"] == 100
    assert snap["api"]["errors_60s"] == 5
    assert snap["api"]["success_rate"] == 0.95
    assert snap["api"]["ok"] is False


def test_api_success_rate_ok_above_threshold():
    m = SLOMetrics()
    for _ in range(99):
        m.record_request(200)
    m.record_request(500)
    snap = m.snapshot()
    assert snap["api"]["success_rate"] == 0.99
    assert snap["api"]["ok"] is True


def test_pipeline_completion_rate():
    m = SLOMetrics()
    for _ in range(19):
        m.record_pipeline_start()
        m.record_pipeline_complete()
    m.record_pipeline_start()
    m.record_pipeline_error()
    snap = m.snapshot()
    assert snap["pipeline"]["total"] == 20
    assert snap["pipeline"]["completed"] == 19
    assert snap["pipeline"]["errored"] == 1
    assert snap["pipeline"]["completion_rate"] == 0.95
    assert snap["pipeline"]["ok"] is True


def test_pipeline_below_target():
    m = SLOMetrics()
    for _ in range(10):
        m.record_pipeline_start()
    for _ in range(8):
        m.record_pipeline_complete()
    for _ in range(2):
        m.record_pipeline_error()
    snap = m.snapshot()
    assert snap["pipeline"]["completion_rate"] == 0.8
    assert snap["pipeline"]["ok"] is False


def test_websocket_stability():
    m = SLOMetrics()
    for _ in range(99):
        m.record_ws_connect()
    m.record_ws_disconnect()
    snap = m.snapshot()
    assert snap["websocket"]["stability"] == 0.99
    assert snap["websocket"]["ok"] is True


@pytest.mark.asyncio
async def test_slo_endpoint_returns_snapshot():
    from app.routes.health import api_slo

    app = FastAPI()
    app.get("/slo")(api_slo)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/slo")
    assert resp.status_code == 200
    data = resp.json()
    assert "api" in data
    assert "pipeline" in data
    assert "websocket" in data
    assert "availability" in data


def test_sim_websocket_handlers_record_connect_and_disconnect():
    """sim.py 的 WebSocket 端点必须接入 SLO connect/disconnect 计数。"""
    from fastapi.testclient import TestClient

    from app.routes.sim import register_sim_routes
    from app.services.map_simulator import Px4MapStateSimulator
    from app.slo import get_slo_metrics

    metrics = get_slo_metrics()
    metrics.reset()

    app = FastAPI()
    register_sim_routes(app, Px4MapStateSimulator())
    client = TestClient(app)

    assert metrics.snapshot()["websocket"]["connects"] == 0
    with client.websocket_connect("/sim/ws/map-state") as websocket:
        websocket.receive_json()
    snap = metrics.snapshot()
    assert snap["websocket"]["connects"] == 1
    assert snap["websocket"]["disconnects"] == 1
    client.close()
    metrics.reset()
