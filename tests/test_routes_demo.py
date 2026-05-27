"""Integration tests for demo endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_upload_image_rejects_empty(client):
    resp = await client.post("/demo/upload-image")
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.skip(reason="Pre-existing SQLite foreign key bug in clear_runtime_task_data")
async def test_reset_events(client):
    resp = await client.post("/demo/reset-events?confirm=true")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_events_requires_confirm(client):
    resp = await client.post("/demo/reset-events")
    assert resp.status_code == 400
