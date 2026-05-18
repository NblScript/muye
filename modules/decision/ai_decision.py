from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from jsonschema import ValidationError, validate

from modules.infra.common import log_event, strip_code_fence
from modules.decision.decision_context import DecisionContextProvider
from modules.infra.event_bus import FileEventBus
from modules.decision.rag.retriever import DecisionRAGRetriever
from modules.infra.weather import WeatherClient


DECISION_SCHEMA = {
    "type": "object",
    "required": ["用药"],
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
        "农事建议": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
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
        decision_context_provider: DecisionContextProvider | None = None,
        rag_retriever: DecisionRAGRetriever | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.weather_client = weather_client
        self.use_mock = use_mock
        self.logger = logger or logging.getLogger("muye.decision")
        self.event_bus = event_bus
        self.decision_context_provider = decision_context_provider
        self.rag_retriever = rag_retriever
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
            decision_context = self._build_decision_context(
                pest_detections=pest_detections,
                weather_data=weather,
                field_context=field_context,
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
            rag_context_text, rag_context = self._build_rag_context_text(
                pest_detections=pest_detections,
                field_context=field_context,
                request_id=request_id,
                client_ip=client_ip,
            )
            structured_input_text = self.build_structured_input_text(
                pest_detections=pest_detections,
                weather_data=weather,
                field_context=field_context,
                decision_context=decision_context,
                rag_context_text=rag_context_text,
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
                    payload={"decision": decision, "rag_context": rag_context},
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
                "decision_context": decision_context,
                "rag_context": rag_context,
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
        decision_context: dict[str, Any] | None = None,
        rag_context_text: str = "",
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
        optional_context_text = ""
        if decision_context:
            optional_context_text = (
                "补充决策参考（可选，不存在时可忽略）：\n"
                f"{json.dumps(decision_context, ensure_ascii=False)}\n"
            )
        rag_context_block = f"{rag_context_text}\n" if rag_context_text else ""
        return (
            "请基于以下农田结构化信息输出严格 JSON，不要输出解释。\n"
            f"地块名称：{field_context.get('name', '未知地块')}\n"
            f"地块面积：{field_context.get('area_mu', '未配置')}亩\n"
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
            f"{optional_context_text}"
            f"{rag_context_block}"
            "注意：飞行路径、高度、速度、喷洒速率、覆盖区域和气象限制由系统 planner 生成，"
            "不要输出任何飞控参数。\n"
            "必须根据地块面积、害虫数量、天气条件和推荐配比给出“用药.总量”；"
            "总量必须是本次作业全田总用量，不是亩用量，且必须包含明确数字和单位，例如“1.2L”或“1200mL”；"
            "禁止写“适量”“按标签”“按需”等无法计算的总量。\n"
            "输出 JSON Schema 关键字段："
            "用药.农药名称/浓度/配比/总量/安全提示，"
            "可选字段为农事建议。"
        )

    def _build_rag_context_text(
        self,
        *,
        pest_detections: list[dict[str, Any]],
        field_context: dict[str, Any],
        request_id: str,
        client_ip: str,
    ) -> tuple[str, dict[str, Any]]:
        if self.rag_retriever is None:
            return "", {}

        pest_types = [
            str(detection.get("pest_type", "")).strip()
            for detection in pest_detections
            if str(detection.get("pest_type", "")).strip()
        ]
        crop_cycle = field_context.get("crop_cycle")
        crop_name = None
        if isinstance(crop_cycle, dict):
            crop_candidate = crop_cycle.get("crop_name")
            if isinstance(crop_candidate, str) and crop_candidate.strip():
                crop_name = crop_candidate.strip()

        if self.event_bus:
            self.event_bus.publish(
                request_id=request_id,
                stage="rag",
                status="running",
                message="正在检索 RAG 决策知识",
                payload={"pest_types": pest_types, "crop_name": crop_name},
            )

        try:
            retrieved = self.rag_retriever.retrieve(
                pest_types=pest_types,
                crop_name=crop_name,
                field_context=field_context,
            )
            rag_context_text = retrieved.to_prompt_text()

            def _docs_to_list(docs, scores):
                return [
                    {"content": doc.page_content, "score": round(s, 3), "metadata": doc.metadata}
                    for doc, s in zip(docs, scores)
                ]

            rag_context = {
                "pesticides": _docs_to_list(retrieved.pesticides, retrieved.pesticide_scores),
                "historical_cases": _docs_to_list(retrieved.historical_cases, retrieved.decision_scores),
                "knowledge": _docs_to_list(retrieved.knowledge_chunks, retrieved.knowledge_scores),
                "pest_types": pest_types,
                "crop_name": crop_name,
            }

            if self.event_bus:
                self.event_bus.publish(
                    request_id=request_id,
                    stage="rag",
                    status="completed",
                    message="RAG 决策知识检索完成",
                    payload={
                        "pest_types": pest_types,
                        "crop_name": crop_name,
                        "pesticide_count": len(retrieved.pesticides),
                        "historical_case_count": len(retrieved.historical_cases),
                    },
                )
            return rag_context_text, rag_context
        except Exception as exc:
            if self.event_bus:
                self.event_bus.publish(
                    request_id=request_id,
                    stage="rag",
                    status="error",
                    message="RAG 决策知识检索失败，已降级为基础决策",
                    payload={
                        "pest_types": pest_types,
                        "crop_name": crop_name,
                        "error": str(exc),
                    },
                )
            log_event(
                self.logger,
                logging.WARNING,
                "RAG 决策知识检索失败，已退回基础决策输入",
                request_id=request_id,
                client_ip=client_ip,
                error=str(exc),
                pest_types=pest_types,
                crop_name=crop_name or "",
            )
            return "", {}

    def _build_decision_context(
        self,
        *,
        pest_detections: list[dict[str, Any]],
        weather_data: dict[str, Any],
        field_context: dict[str, Any],
        request_id: str,
        client_ip: str,
    ) -> dict[str, Any]:
        if self.decision_context_provider is None:
            return {}
        try:
            return self.decision_context_provider.build_context(
                request_id=request_id,
                pest_detections=pest_detections,
                weather_data=weather_data,
                field_context=field_context,
            )
        except Exception as exc:
            log_event(
                self.logger,
                logging.WARNING,
                "决策增强上下文构建失败，已退回基础决策输入",
                request_id=request_id,
                client_ip=client_ip,
                error=str(exc),
            )
            return {}

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
                        "顶层必须包含“用药”，可选“农事建议”。"
                        "禁止输出飞行路径、高度、速度、喷洒速率、覆盖区域、气象限制等飞控字段。"
                        "所有字段名必须使用中文，且必填字段不能为空字符串。"
                        "“用药.总量”必须是本次作业全田总用量，并包含明确数字和单位。"
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
                        "顶层只保留“用药”和可选“农事建议”。"
                        "所有必填字段必须存在且不能为空。"
                        "“用药.总量”必须是本次作业全田总用量，并包含明确数字和单位。"
                        "不要生成任何飞控字段。"
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
        elif "用药" in payload:
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
        if "用药" in payload:
            sanitized = {"用药": payload["用药"]}
            if "农事建议" in payload:
                sanitized["农事建议"] = payload["农事建议"]
            return sanitized
        return payload

    def _normalize_decision_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        medication = payload.get("用药", {}) if isinstance(payload.get("用药"), dict) else {}

        return {
            "用药": {
                "农药名称": self._normalize_text(medication.get("农药名称")),
                "浓度": self._normalize_text(medication.get("浓度")),
                "配比": self._normalize_text(medication.get("配比")),
                "总量": self._normalize_text(medication.get("总量")),
                "安全提示": self._normalize_string_list(medication.get("安全提示")),
            },
            "农事建议": self._normalize_string_list(payload.get("农事建议")),
        }

    def _validate_decision_payload(self, payload: dict[str, Any]) -> None:
        try:
            validate(instance=payload, schema=DECISION_SCHEMA)
        except ValidationError as exc:
            raise DecisionEngineError(f"千问返回 JSON 结构不合法: {exc.message}") from exc

        total_amount = str(payload["用药"].get("总量") or "").strip()
        if not self._has_measurable_total_amount(total_amount):
            raise DecisionEngineError("千问返回 JSON 结构不合法: 用药.总量必须包含明确数字和单位")

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
        medication = payload["用药"]
        fallback_medication = fallback["用药"]
        for key in ["农药名称", "浓度", "配比", "总量"]:
            if not medication.get(key):
                medication[key] = fallback_medication[key]
        if not self._has_measurable_total_amount(medication.get("总量")):
            medication["总量"] = fallback_medication["总量"]
        if not medication.get("安全提示"):
            medication["安全提示"] = fallback_medication["安全提示"]
        if not payload.get("农事建议"):
            payload["农事建议"] = fallback.get("农事建议", [])

        return payload

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_number(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _normalize_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _has_measurable_total_amount(self, value: Any) -> bool:
        text = self._normalize_text(value).replace(" ", "")
        if not text:
            return False
        return bool(re.search(r"\d+(?:\.\d+)?\s*(mL|ml|ML|毫升|L|l|升|g|G|kg|KG|克|千克)", text))

    def _build_mock_decision(
        self,
        pest_detections: list[dict[str, Any]],
        field_context: dict[str, Any],
        weather_data: dict[str, Any],
    ) -> dict[str, Any]:
        primary_pest = pest_detections[0]["pest_type"] if pest_detections else "unknown-pest"
        total_targets = max(len(pest_detections), 1)
        area_mu = self._normalize_number(field_context.get("area_mu")) or 10.0
        total_amount_l = round(max(area_mu, 1.0) * 0.12 + total_targets * 0.15, 2)

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
            "农事建议": [
                f"优先针对{primary_pest}高发区域安排喷洒作业",
                f"当前天气{weather_data['summary']}，作业前再次核验实时风速与湿度",
            ],
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
