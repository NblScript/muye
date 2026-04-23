from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from modules.infra.common import generate_request_id


@dataclass(slots=True)
class VirtualDroneSettings:
    host: str
    port: int
    api_key: str
    allowed_ips: list[str]


@dataclass
class MissionRecord:
    task_id: str
    request_id: str
    accepted: bool
    status: str
    progress: int
    instruction: dict[str, Any]
    medication: dict[str, Any]
    weather: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    message: str = "任务已接收"
    current_waypoint_index: int = 0


class MissionRequest(BaseModel):
    request_id: str = Field(min_length=1)
    medication: dict[str, Any]
    instruction: dict[str, Any]
    weather: dict[str, Any]


class VirtualDroneService:
    def __init__(self, settings: VirtualDroneSettings, logger: logging.Logger | None = None) -> None:
        self.settings = settings
        self.logger = logger or logging.getLogger("muye.virtual_drone")
        self._missions: dict[str, MissionRecord] = {}
        self._lock = asyncio.Lock()

    async def create_mission(self, payload: MissionRequest) -> MissionRecord:
        task_id = f"vd-{generate_request_id()[:10]}"
        record = MissionRecord(
            task_id=task_id,
            request_id=payload.request_id,
            accepted=True,
            status="queued",
            progress=5,
            instruction=payload.instruction,
            medication=payload.medication,
            weather=payload.weather,
            message="虚拟无人机任务已排队",
        )
        async with self._lock:
            self._missions[task_id] = record
        asyncio.create_task(self._advance_mission(task_id))
        return record

    async def get_mission(self, task_id: str) -> MissionRecord:
        async with self._lock:
            mission = self._missions.get(task_id)
            if not mission:
                raise KeyError(task_id)
            return mission

    async def _advance_mission(self, task_id: str) -> None:
        stages = [
            ("takeoff", 20, "虚拟无人机起飞中"),
            ("enroute", 45, "虚拟无人机前往作业区域"),
            ("spraying", 75, "虚拟无人机喷洒中"),
            ("returning", 92, "虚拟无人机返航中"),
            ("completed", 100, "虚拟无人机任务完成"),
        ]
        for index, (status, progress, message) in enumerate(stages, start=1):
            await asyncio.sleep(0.35)
            async with self._lock:
                mission = self._missions.get(task_id)
                if not mission:
                    return
                mission.status = status
                mission.progress = progress
                mission.message = message
                mission.current_waypoint_index = min(
                    index,
                    max(len(mission.instruction.get("飞行路径", [])) - 1, 0),
                )
                mission.updated_at = time.time()


def load_virtual_drone_settings() -> VirtualDroneSettings:
    allowed_ips = [
        item.strip()
        for item in os.getenv("VIRTUAL_DRONE_ALLOWED_IPS", "127.0.0.1,::1").split(",")
        if item.strip()
    ]
    return VirtualDroneSettings(
        host=os.getenv("VIRTUAL_DRONE_HOST", "127.0.0.1"),
        port=int(os.getenv("VIRTUAL_DRONE_PORT", "9010")),
        api_key=os.getenv("DRONE_API_KEY", "virtual-drone-token"),
        allowed_ips=allowed_ips,
    )


def _ensure_authorized(settings: VirtualDroneSettings, authorization: str | None, x_api_key: str | None) -> None:
    if not settings.api_key:
        return
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1].strip()
    if bearer == settings.api_key or x_api_key == settings.api_key:
        return
    raise HTTPException(status_code=401, detail="虚拟无人机鉴权失败")


def _ensure_ip_allowed(settings: VirtualDroneSettings, client_ip: str) -> None:
    if not settings.allowed_ips:
        return
    address = ipaddress.ip_address(client_ip)
    for item in settings.allowed_ips:
        if "/" in item:
            if address in ipaddress.ip_network(item, strict=False):
                return
        elif address == ipaddress.ip_address(item):
            return
    raise HTTPException(status_code=403, detail=f"客户端 IP {client_ip} 不在虚拟无人机白名单中")


def _serialize_mission(record: MissionRecord) -> dict[str, Any]:
    return {
        "task_id": record.task_id,
        "request_id": record.request_id,
        "accepted": record.accepted,
        "status": record.status,
        "progress": record.progress,
        "message": record.message,
        "current_waypoint_index": record.current_waypoint_index,
        "instruction": record.instruction,
        "medication": record.medication,
        "weather": record.weather,
    }


def create_virtual_drone_app(
    settings: VirtualDroneSettings | None = None,
    service: VirtualDroneService | None = None,
    logger: logging.Logger | None = None,
) -> FastAPI:
    active_settings = settings or load_virtual_drone_settings()
    active_service = service or VirtualDroneService(active_settings, logger=logger)
    app = FastAPI(title="Muye Virtual Drone API", version="1.0.0")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "port": active_settings.port}

    @app.post("/missions")
    async def create_mission(
        request: Request,
        payload: MissionRequest,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        client_ip = request.client.host if request.client else "127.0.0.1"
        _ensure_authorized(active_settings, authorization, x_api_key)
        _ensure_ip_allowed(active_settings, client_ip)
        record = await active_service.create_mission(payload)
        return _serialize_mission(record)

    @app.get("/missions/{task_id}")
    async def get_mission(
        task_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        client_ip = request.client.host if request.client else "127.0.0.1"
        _ensure_authorized(active_settings, authorization, x_api_key)
        _ensure_ip_allowed(active_settings, client_ip)
        try:
            record = await active_service.get_mission(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="任务不存在") from exc
        return _serialize_mission(record)

    return app
