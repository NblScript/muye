"""Simulation map state endpoints."""

import asyncio
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from models.schemas import SimMapStateResponse
from app.services.map_simulator import Px4MapStateSimulator

# Global simulator instance, set during app initialization
_simulator: Optional[Px4MapStateSimulator] = None


def set_simulator(simulator: Px4MapStateSimulator) -> None:
    """Set the global simulator instance."""
    global _simulator
    _simulator = simulator


def get_simulator() -> Px4MapStateSimulator:
    """Get the global simulator instance."""
    if _simulator is None:
        raise RuntimeError("Simulator not initialized")
    return _simulator


async def get_sim_map_state() -> SimMapStateResponse:
    """Get simulation map state endpoint handler."""
    return get_simulator().snapshot()


async def sim_map_state_ws(websocket: WebSocket) -> None:
    """Simulation map state websocket handler."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_simulator().snapshot().model_dump())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


def register_sim_routes(app: FastAPI, simulator: Px4MapStateSimulator) -> None:
    """Register simulation routes."""
    set_simulator(simulator)
    app.get("/sim/map-state", response_model=SimMapStateResponse)(get_sim_map_state)
    app.get("/api/sim/map-state", include_in_schema=False, response_model=SimMapStateResponse)(get_sim_map_state)
    app.websocket("/sim/ws/map-state")(sim_map_state_ws)
    app.websocket("/api/sim/ws/map-state")(sim_map_state_ws)
