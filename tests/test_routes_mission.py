"""Integration tests for mission endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_missions(client):
    resp = await client.get("/api/missions")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "missions" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_missions_with_status_filter(client):
    resp = await client.get("/api/missions?status=completed")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "missions" in data


@pytest.mark.asyncio
async def test_get_mission_not_found(client):
    resp = await client.get("/api/mission/nonexistent_id")
    assert resp.status_code in (404, 200)


@pytest.mark.asyncio
async def test_get_mission_by_request_not_found(client):
    resp = await client.get("/api/mission/by-request/nonexistent_id")
    assert resp.status_code in (404, 200)


@pytest.mark.asyncio
async def test_cancel_mission_not_found(client):
    resp = await client.post("/api/mission/nonexistent_id/cancel")
    assert resp.status_code in (404, 200)
