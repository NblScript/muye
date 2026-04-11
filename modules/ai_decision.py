from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
        use_mock: bool = False,
        timeout_seconds: float = 30,
        logger: logging.Logger | None = None,
        event_bus: FileEventBus | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.weather_client = weather_client
        self.use_mock = use_mock
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
            if self.use_mock:
                decision = self._build_mock_decision(
                    pest_detections=pest_detections,
                    field_context=field_context,
                    weather_data=weather,
                )
            else:
                decision = await self._request_qwen_decision(
                    structured_input_text=structured_input_text,
                    request_id=request_id,
                    client_ip=client_ip,
                    pest_detections=pest_detections,
                    field_context=field_context,
                    weather_data=weather,
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
        pest_detections: list[dict[str, Any]],
        field_context: dict[str, Any],
        weather_data: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.api_url:
            raise DecisionEngineError("缺少 QWEN_API_URL 配置")
        if not self.api_key:
            raise DecisionEngineError("缺少 QWEN_API_KEY 配置")

        raw_payload = await self._invoke_qwen(
            request_id=request_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是农业植保决策助手。"
                        "必须只输出一个 JSON 对象。"
                        "顶层只能包含“用药”和“指令”两个字段。"
                        "所有字段名必须使用中文，且必填字段不能为空字符串。"
                    ),
                },
                {"role": "user", "content": structured_input_text},
            ],
        )
        normalized = self._normalize_decision_payload(
            self._sanitize_decision_payload(self._extract_decision_content(raw_payload))
        )

        try:
            self._validate_decision_payload(normalized)
            return normalized
        except DecisionEngineError as first_error:
            repaired_payload = await self._repair_qwen_decision(
                request_id=request_id,
                structured_input_text=structured_input_text,
                invalid_payload=normalized,
                validation_error=str(first_error),
            )
            repaired = self._normalize_decision_payload(
                self._sanitize_decision_payload(self._extract_decision_content(repaired_payload))
            )
            try:
                self._validate_decision_payload(repaired)
                return repaired
            except DecisionEngineError:
                fallback = self._build_mock_decision(
                    pest_detections=pest_detections,
                    field_context=field_context,
                    weather_data=weather_data,
                )
                merged = self._merge_with_fallback(repaired, fallback)
                merged = self._normalize_decision_payload(merged)
                merged = self._apply_schema_guards(merged, fallback)
                self._validate_decision_payload(merged)
                return merged

    async def _invoke_qwen(
        self,
        request_id: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        response = await self._client.post(
            self._resolve_chat_completions_url(self.api_url),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Request-ID": request_id,
            },
            json={
                "model": self.model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": messages,
            },
        )
        response.raise_for_status()
        return response.json()

    async def _repair_qwen_decision(
        self,
        request_id: str,
        structured_input_text: str,
        invalid_payload: dict[str, Any],
        validation_error: str,
    ) -> dict[str, Any]:
        return await self._invoke_qwen(
            request_id=request_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是农业植保 JSON 修复助手。"
                        "请把输入修复为合法 JSON。"
                        "顶层只能保留“用药”和“指令”。"
                        "所有必填字段必须存在且不能为空。"
                        "不要输出解释。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"原始农业上下文：\n{structured_input_text}\n\n"
                        f"校验错误：{validation_error}\n\n"
                        f"待修复 JSON：\n{json.dumps(invalid_payload, ensure_ascii=False)}"
                    ),
                },
            ],
        )

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

    def _sanitize_decision_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if {"用药", "指令"}.issubset(payload):
            return {
                "用药": payload["用药"],
                "指令": payload["指令"],
            }
        return payload

    def _normalize_decision_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        medication = payload.get("用药", {}) if isinstance(payload.get("用药"), dict) else {}
        instruction = payload.get("指令", {}) if isinstance(payload.get("指令"), dict) else {}
        coverage = instruction.get("覆盖区域", {}) if isinstance(instruction.get("覆盖区域"), dict) else {}
        restrictions = instruction.get("气象限制", {}) if isinstance(instruction.get("气象限制"), dict) else {}

        return {
            "用药": {
                "农药名称": self._normalize_text(medication.get("农药名称")),
                "浓度": self._normalize_text(medication.get("浓度")),
                "配比": self._normalize_text(medication.get("配比")),
                "总量": self._normalize_text(medication.get("总量")),
                "安全提示": self._normalize_string_list(medication.get("安全提示")),
            },
            "指令": {
                "飞行路径": self._normalize_coordinate_pairs(instruction.get("飞行路径")),
                "高度": self._normalize_number(instruction.get("高度")),
                "速度": self._normalize_number(instruction.get("速度")),
                "喷洒速率": self._normalize_number(instruction.get("喷洒速率")),
                "覆盖区域": {
                    "type": self._normalize_text(coverage.get("type")),
                    "coordinates": self._normalize_coordinate_pairs(coverage.get("coordinates")),
                },
                "气象限制": {
                    "最大风速": self._normalize_number(restrictions.get("最大风速")),
                    "最低温度": self._normalize_number(restrictions.get("最低温度")),
                    "最高温度": self._normalize_number(restrictions.get("最高温度")),
                    "最大湿度": self._normalize_number(restrictions.get("最大湿度")),
                },
            },
        }

    def _validate_decision_payload(self, payload: dict[str, Any]) -> None:
        try:
            validate(instance=payload, schema=DECISION_SCHEMA)
        except ValidationError as exc:
            raise DecisionEngineError(f"千问返回 JSON 结构不合法: {exc.message}") from exc

        restrictions = payload["指令"]["气象限制"]
        if restrictions["最低温度"] > restrictions["最高温度"]:
            raise DecisionEngineError("气象限制中的最低温度不能大于最高温度")

    def _merge_with_fallback(self, value: Any, fallback: Any) -> Any:
        if isinstance(fallback, dict):
            source = value if isinstance(value, dict) else {}
            return {
                key: self._merge_with_fallback(source.get(key), fallback_value)
                for key, fallback_value in fallback.items()
            }

        if isinstance(fallback, list):
            if isinstance(value, list) and value:
                if fallback and isinstance(fallback[0], (dict, list)):
                    template = fallback[0]
                    return [self._merge_with_fallback(item, template) for item in value]
                filtered = [item for item in value if item not in (None, "", [])]
                return filtered or fallback
            return fallback

        if isinstance(fallback, str):
            candidate = self._normalize_text(value)
            return candidate or fallback

        if isinstance(fallback, (int, float)):
            candidate = self._normalize_number(value)
            return candidate if candidate is not None else fallback

        return value if value is not None else fallback

    def _apply_schema_guards(
        self,
        payload: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        instruction = payload["指令"]
        fallback_instruction = fallback["指令"]

        instruction["高度"] = self._coalesce_positive_number(
            instruction.get("高度"),
            fallback_instruction["高度"],
        )
        instruction["速度"] = self._coalesce_positive_number(
            instruction.get("速度"),
            fallback_instruction["速度"],
        )
        instruction["喷洒速率"] = self._coalesce_positive_number(
            instruction.get("喷洒速率"),
            fallback_instruction["喷洒速率"],
        )

        restrictions = instruction["气象限制"]
        fallback_restrictions = fallback_instruction["气象限制"]
        restrictions["最大风速"] = self._coalesce_positive_number(
            restrictions.get("最大风速"),
            fallback_restrictions["最大风速"],
        )
        restrictions["最大湿度"] = self._coalesce_bounded_number(
            restrictions.get("最大湿度"),
            fallback_restrictions["最大湿度"],
            lower=0,
            upper=100,
        )

        if restrictions["最低温度"] is None:
            restrictions["最低温度"] = fallback_restrictions["最低温度"]
        if restrictions["最高温度"] is None:
            restrictions["最高温度"] = fallback_restrictions["最高温度"]
        if restrictions["最低温度"] > restrictions["最高温度"]:
            restrictions["最低温度"] = fallback_restrictions["最低温度"]
            restrictions["最高温度"] = fallback_restrictions["最高温度"]

        if len(instruction["飞行路径"]) < 2:
            instruction["飞行路径"] = fallback_instruction["飞行路径"]
        if len(instruction["覆盖区域"]["coordinates"]) < 3:
            instruction["覆盖区域"]["coordinates"] = fallback_instruction["覆盖区域"]["coordinates"]
        if not instruction["覆盖区域"]["type"]:
            instruction["覆盖区域"]["type"] = fallback_instruction["覆盖区域"]["type"]

        medication = payload["用药"]
        fallback_medication = fallback["用药"]
        for key in ["农药名称", "浓度", "配比", "总量"]:
            if not medication.get(key):
                medication[key] = fallback_medication[key]
        if not medication.get("安全提示"):
            medication["安全提示"] = fallback_medication["安全提示"]

        return payload

    def _coalesce_positive_number(self, value: Any, fallback: float) -> float:
        candidate = self._normalize_number(value)
        if candidate is None or candidate <= 0:
            return float(fallback)
        return candidate

    def _coalesce_bounded_number(
        self,
        value: Any,
        fallback: float,
        *,
        lower: float,
        upper: float,
    ) -> float:
        candidate = self._normalize_number(value)
        if candidate is None or candidate < lower or candidate > upper:
            return float(fallback)
        return candidate

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _normalize_number(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _normalize_coordinate_pairs(self, value: Any) -> list[list[float]]:
        if not isinstance(value, list):
            return []

        result: list[list[float]] = []
        for item in value:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            try:
                result.append([float(item[0]), float(item[1])])
            except (TypeError, ValueError):
                continue
        return result

    def _build_mock_decision(
        self,
        pest_detections: list[dict[str, Any]],
        field_context: dict[str, Any],
        weather_data: dict[str, Any],
    ) -> dict[str, Any]:
        geofence = field_context.get("geofence", [])
        if len(geofence) < 3:
            raise DecisionEngineError("模拟决策需要至少三个围栏坐标点")

        primary_pest = pest_detections[0]["pest_type"] if pest_detections else "unknown-pest"
        total_targets = max(len(pest_detections), 1)
        total_amount_l = round(6 + total_targets * 2.5, 1)

        return {
            "用药": {
                "农药名称": f"示范药剂-{primary_pest}",
                "浓度": "20%",
                "配比": "1:1200",
                "总量": f"{total_amount_l}L",
                "安全提示": [
                    "作业人员佩戴防护服和护目镜",
                    "喷洒期间远离水源和人畜活动区域",
                ],
            },
            "指令": {
                "飞行路径": [geofence[0], geofence[1], geofence[2]],
                "高度": 3.5,
                "速度": 2.2,
                "喷洒速率": 1.1,
                "覆盖区域": {
                    "type": "polygon",
                    "coordinates": geofence[:3],
                },
                "气象限制": {
                    "最大风速": max(float(weather_data["wind_speed"]) + 1.0, 4.0),
                    "最低温度": min(float(weather_data["temperature"]) - 8.0, float(weather_data["temperature"])),
                    "最高温度": max(float(weather_data["temperature"]) + 8.0, float(weather_data["temperature"])),
                    "最大湿度": max(float(weather_data["humidity"]) + 10.0, 85.0),
                },
            },
        }

    def _resolve_chat_completions_url(self, api_url: str) -> str:
        parsed = urlsplit(api_url)
        path = parsed.path.rstrip("/")
        if path.endswith("/chat/completions"):
            return api_url

        if not path:
            path = "/chat/completions"
        else:
            path = f"{path}/chat/completions"

        return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
