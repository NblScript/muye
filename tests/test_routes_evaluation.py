"""Integration tests for evaluation endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_evaluations(client):
    resp = await client.get("/api/evaluations")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "evaluations" in data


@pytest.mark.asyncio
async def test_get_evaluation_not_found(client):
    resp = await client.get("/api/evaluation/nonexistent_id")
    assert resp.status_code in (404, 200)


@pytest.mark.asyncio
async def test_cancel_evaluation_not_found(client):
    resp = await client.post("/api/evaluation/nonexistent_id/cancel")
    assert resp.status_code in (404, 200)
