from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from jsonschema import ValidationError, validate

from modules.common import log_event, strip_code_fence
from modules.event_bus import FileEventBus
from modules.weather_integration import WeatherClient


DECISION_SCHEMA = {
    "type": "object",
    "required": ["用药", "指令"],
    "additionalProperties": False,
    "properties": {
        "用药": {
            "type": "object",
            "required": ["农药名称", "浓度", "配比", "总量", "安全提示"],
            "additionalProperties": False,
            "properties": {
                "农药名称": {"type": "string", "minLength": 1},
                "浓度": {"type": "string", "minLength": 1},
                "配比": {"type": "string", "minLength": 1},
                "总量": {"type": "string", "minLength": 1},
                "安全提示": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "指令": {
            "type": "object",
            "required": ["飞行路径", "高度", "速度", "喷洒速率", "覆盖区域", "气象限制"],
            "additionalProperties": False,
            "properties": {
                "飞行路径": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 2,
                        "items": {"type": "number"},
                    },
                },
                "高度": {"type": "number", "minimum": 0.1},
                "速度": {"type": "number", "minimum": 0.1},
                "喷洒速率": {"type": "number", "minimum": 0.01},
                "覆盖区域": {
                    "type": "object",
                    "required": ["type", "coordinates"],
                    "additionalProperties": False,
                    "properties": {
                        "type": {"type": "string", "minLength": 1},
                        "coordinates": {
                            "type": "array",
                            "minItems": 3,
                            "items": {
                                "type": "array",
                                "minItems": 2,
                                "maxItems": 2,
                                "items": {"type": "number"},
                            },
                        },
                    },
                },
                "气象限制": {
                    "type": "object",
                    "required": ["最大风速", "最低温度", "最高温度", "最大湿度"],
                    "additionalProperties": False,
                    "properties": {
                        "最大风速": {"type": "number", "minimum": 0.1},
                        "最低温度": {"type": "number"},
                        "最高温度": {"type": "number"},
                        "最大湿度": {"type": "number", "minimum": 0, "maximum": 100},
                    },
                },
            },
        },
    },
}


class DecisionEngineError(RuntimeError):
    """AI 决策阶段错误。"""


class DecisionEngine:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        weather_client: WeatherClient,
        timeout_seconds: float = 30,
        logger: logging.Logger | None = None,
        event_bus: FileEventBus | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.weather_client = weather_client
        self.logger = logger or logging.getLogger("muye.decision")
        self.event_bus = event_bus
        self._client = httpx.AsyncClient(timeout=timeout_seconds, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def generate_decision(
        self,
        pest_detections: list[dict[str, Any]],
        field_context: dict[str, Any],
        request_id: str,
        client_ip: str = "127.0.0.1",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        location = field_context.get("location", {})
        try:
            weather_location = (
                field_context.get("weather_location")
                or location.get("city")
                or (
                    f"{location.get('longitude')},{location.get('latitude')}"
                    if location.get("longitude") is not None and location.get("latitude") is not None
                    else None
                )
            )
            if not weather_location:
                raise DecisionEngineError("缺少 weather_location 或 location.city 配置")
            if self.event_bus:
                self.event_bus.publish(
                    request_id=request_id,
                    stage="weather",
                    status="running",
                    message="正在获取天气信息",
                    payload={"location_query": str(weather_location)},
                )
            weather = await self.weather_client.fetch_current_weather(
                location_query=str(weather_location),
                request_id=request_id,
                client_ip=client_ip,
            )
            if self.event_bus:
                self.event_bus.publish(
                    request_id=request_id,
                    stage="weather",
                    status="completed",
                    message="天气信息获取完成",
                    payload={"location_query": str(weather_location), "weather": weather},
                )
            structured_input_text = self.build_structured_input_text(
                pest_detections=pest_detections,
                weather_data=weather,
                field_context=field_context,
            )
            if self.event_bus:
                self.event_bus.publish(
                    request_id=request_id,
                    stage="decision",
                    status="running",
                    message="正在生成千问决策",
                    payload={},
                )
            decision = await self._request_qwen_decision(
                structured_input_text=structured_input_text,
                request_id=request_id,
                client_ip=client_ip,
            )
            if self.event_bus:
                self.event_bus.publish(
                    request_id=request_id,
                    stage="decision",
                    status="completed",
                    message="千问决策生成完成",
                    payload={"decision": decision},
                )
            log_event(
                self.logger,
                logging.INFO,
                "AI 决策生成完成",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                pesticide=decision["用药"]["农药名称"],
            )
            return {
                "weather": weather,
                "decision": decision,
                "structured_input_text": structured_input_text,
            }
        except Exception as exc:
            if self.event_bus:
                self.event_bus.publish(
                    request_id=request_id,
                    stage="decision",
                    status="error",
                    message="AI 决策生成失败",
                    payload={"error": str(exc)},
                )
            log_event(
                self.logger,
                logging.ERROR,
                "AI 决策生成失败",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
            )
            raise DecisionEngineError(str(exc)) from exc

    def build_structured_input_text(
        self,
        pest_detections: list[dict[str, Any]],
        weather_data: dict[str, Any],
        field_context: dict[str, Any],
    ) -> str:
        detection_lines = []
        for index, detection in enumerate(pest_detections, start=1):
            detection_lines.append(
                (
                    f"{index}. 害虫类型={detection['pest_type']}，"
                    f"置信度={detection['confidence']}，"
                    f"位置={json.dumps(detection['position'], ensure_ascii=False)}"
                )
            )

        location = field_context.get("location", {})
        geofence = json.dumps(field_context.get("geofence", []), ensure_ascii=False)
        return (
            "请基于以下农田结构化信息输出严格 JSON，不要输出解释。\n"
            f"地块名称：{field_context.get('name', '未知地块')}\n"
            f"地块坐标：纬度={location.get('latitude')}，经度={location.get('longitude')}\n"
            f"天气查询地点：{field_context.get('weather_location') or location.get('city', '未配置')}\n"
            f"地理围栏：{geofence}\n"
            "实时天气："
            f"温度={weather_data['temperature']}℃，"
            f"湿度={weather_data['humidity']}%，"
            f"风向={weather_data['wind_direction']}，"
            f"风力等级={weather_data['wind_scale_text']}，"
            f"推算风速上限={weather_data['wind_speed']}m/s，"
            f"天气概况={weather_data['summary']}\n"
            "害虫检测结果：\n"
            f"{chr(10).join(detection_lines)}\n"
            "输出 JSON Schema 关键字段："
            "用药.农药名称/浓度/配比/总量/安全提示，"
            "指令.飞行路径/高度/速度/喷洒速率/覆盖区域/气象限制。"
        )

    async def _request_qwen_decision(
        self,
        structured_input_text: str,
        request_id: str,
        client_ip: str,
    ) -> dict[str, Any]:
        if not self.api_url:
            raise DecisionEngineError("缺少 QWEN_API_URL 配置")
        if not self.api_key:
            raise DecisionEngineError("缺少 QWEN_API_KEY 配置")

        response = await self._client.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Request-ID": request_id,
            },
            json={
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是农业植保决策助手。"
                            "必须输出可被 json.loads 直接解析的 JSON，"
                            "且字段名严格使用中文。"
                        ),
                    },
                    {"role": "user", "content": structured_input_text},
                ],
            },
        )
        response.raise_for_status()
        parsed = self._extract_decision_content(response.json())
        try:
            validate(instance=parsed, schema=DECISION_SCHEMA)
        except ValidationError as exc:
            raise DecisionEngineError(f"千问返回 JSON 结构不合法: {exc.message}") from exc

        restrictions = parsed["指令"]["气象限制"]
        if restrictions["最低温度"] > restrictions["最高温度"]:
            raise DecisionEngineError("气象限制中的最低温度不能大于最高温度")
        return parsed

    def _extract_decision_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "choices" in payload and payload["choices"]:
            message = payload["choices"][0].get("message", {})
            content = message.get("content")
        elif "output" in payload and isinstance(payload["output"], dict):
            content = payload["output"].get("text") or payload["output"].get("content")
        elif {"用药", "指令"}.issubset(payload):
            return payload
        else:
            raise DecisionEngineError("无法从千问响应中提取内容")

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(str(item["text"]))
                elif isinstance(item, str):
                    text_parts.append(item)
            content = "".join(text_parts)

        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise DecisionEngineError("千问响应 content 类型不受支持")

        normalized = strip_code_fence(content)
        try:
            return json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise DecisionEngineError(f"千问返回内容不是合法 JSON: {exc}") from exc
