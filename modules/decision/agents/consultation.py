from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
from jsonschema import ValidationError, validate

from modules.decision.agents.expert_roles import EXPERT_OUTPUT_SCHEMA, EXPERT_ROLES
from modules.decision.agents.voting import weighted_vote
from modules.decision.rag.retriever import DecisionRAGRetriever
from modules.infra.event_bus import FileEventBus


class ExpertConsultation:
    """多智能体专家会诊编排。"""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        rag_retriever: DecisionRAGRetriever | None = None,
        event_bus: FileEventBus | None = None,
        logger: logging.Logger | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.rag_retriever = rag_retriever
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger(__name__)
        self.timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def consult(
        self,
        pest_detections: list[dict[str, Any]],
        weather_data: dict[str, Any],
        field_context: dict[str, Any],
        decision_context: dict[str, Any] | None = None,
        rag_context_text: str = "",
        request_id: str = "",
        client_ip: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """执行多智能体会诊，返回与 DECISION_SCHEMA 兼容的结果。"""
        self.logger.info(
            "多智能体会诊开始 request_id=%s pest_count=%d",
            request_id,
            len(pest_detections),
        )
        self._publish_event(
            request_id, "consultation_started", "多智能体会诊启动",
            {"roles": list(EXPERT_ROLES.keys())},
        )

        # 构建公共上下文
        pest_names = ", ".join(
            d.get("pest_type", "") for d in pest_detections if d.get("pest_type")
        )
        crop_name = field_context.get("crop_name", "未知作物")
        common_context = self._build_common_context(
            pest_detections, weather_data, field_context, decision_context, rag_context_text
        )

        # 为每个角色构建角色特定的 RAG 查询并检索
        role_knowledge = await self._retrieve_role_knowledge(
            pest_names, crop_name, weather_data
        )

        # 并行调用所有专家
        tasks = {
            role: self._ask_expert(
                role, common_context, role_knowledge.get(role, ""), request_id
            )
            for role in EXPERT_ROLES
        }
        results = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        # 收集结果
        opinions: dict[str, dict[str, Any]] = {}
        failed_roles: list[str] = []
        for role, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                self.logger.warning(
                    "专家 %s 调用失败: %s", EXPERT_ROLES[role]["name"], result
                )
                failed_roles.append(role)
                self._publish_event(
                    request_id, "expert_failed",
                    f"{EXPERT_ROLES[role]['name']}调用失败",
                    {"role": role, "error": str(result)},
                )
            else:
                opinions[role] = result
                self._publish_event(
                    request_id, "expert_opinion",
                    f"{EXPERT_ROLES[role]['name']}意见已收集",
                    {
                        "role": role,
                        "农药名称": result.get("用药", {}).get("农药名称", ""),
                    },
                )

        # 投票汇总
        final = weighted_vote(opinions, failed_roles)

        self.logger.info(
            "多智能体会诊完成 request_id=%s confidence=%.2f agreement=%s active=%d failed=%d",
            request_id,
            final.get("confidence", 0),
            final.get("agreement", ""),
            len(opinions),
            len(failed_roles),
        )
        self._publish_event(
            request_id, "consultation_completed", "多智能体会诊完成",
            {
                "confidence": final.get("confidence", 0),
                "agreement": final.get("agreement", ""),
                "active_experts": len(opinions),
                "failed_experts": len(failed_roles),
            },
        )

        return final

    def _build_common_context(
        self,
        pest_detections: list[dict[str, Any]],
        weather_data: dict[str, Any],
        field_context: dict[str, Any],
        decision_context: dict[str, Any] | None,
        rag_context_text: str,
    ) -> str:
        """构建所有专家共享的上下文文本。"""
        parts = []

        # 害虫检测
        if pest_detections:
            parts.append("## 害虫检测结果")
            for d in pest_detections:
                parts.append(
                    f"- 害虫：{d.get('pest_type', '未知')} "
                    f"置信度：{d.get('confidence', 0):.1%}"
                )

        # 天气
        if weather_data:
            parts.append("## 气象数据")
            parts.append(
                f"- 温度：{weather_data.get('temperature', 'N/A')}°C "
                f"湿度：{weather_data.get('humidity', 'N/A')}% "
                f"天气：{weather_data.get('weather_desc', 'N/A')}"
            )

        # 农田
        if field_context:
            parts.append("## 农田信息")
            parts.append(
                f"- 农田：{field_context.get('name', 'N/A')} "
                f"面积：{field_context.get('area_mu', 'N/A')}亩 "
                f"作物：{field_context.get('crop_name', 'N/A')}"
            )

        # 决策上下文
        if decision_context:
            parts.append("## 辅助决策数据")
            parts.append(json.dumps(decision_context, ensure_ascii=False, indent=2))

        # RAG 上下文
        if rag_context_text:
            parts.append("## 知识库检索结果")
            parts.append(rag_context_text)

        return "\n".join(parts)

    async def _retrieve_role_knowledge(
        self,
        pest_names: str,
        crop_name: str,
        weather_data: dict[str, Any],
    ) -> dict[str, str]:
        """为每个角色检索 RAG 知识。"""
        if not self.rag_retriever:
            return {}

        role_knowledge: dict[str, str] = {}
        for role, config in EXPERT_ROLES.items():
            try:
                query = config["retrieval_query_template"].format(
                    pest_names=pest_names, crop_name=crop_name,
                )
                context = self.rag_retriever.retrieve(
                    pest_types=[pest_names],
                    crop_name=crop_name,
                )
                role_knowledge[role] = context.to_prompt_text()
            except Exception as e:
                self.logger.warning(
                    "角色 %s RAG 检索失败: %s", config["name"], e
                )
                role_knowledge[role] = ""

        return role_knowledge

    async def _ask_expert(
        self,
        role: str,
        common_context: str,
        role_knowledge: str,
        request_id: str,
    ) -> dict[str, Any]:
        """调用单个专家角色。"""
        config = EXPERT_ROLES[role]

        # 构建角色特定的用户 prompt
        knowledge_section = ""
        if role_knowledge:
            knowledge_section = f"\n## {config['retrieval_focus']}（RAG 检索）\n{role_knowledge}\n"

        user_prompt = (
            f"## 当前情况\n{common_context}\n"
            f"{knowledge_section}"
            f"\n请从{config['name']}的专业角度给出用药建议。输出 JSON。"
        )

        # 调用 LLM
        raw = await self._invoke_qwen(
            request_id=request_id,
            messages=[
                {"role": "system", "content": config["system_prompt"]},
                {"role": "user", "content": user_prompt},
            ],
        )

        # 解析和校验
        opinion = self._extract_and_validate(raw)

        # 校验失败时尝试修复
        if opinion is None:
            repair_raw = await self._invoke_qwen(
                request_id=request_id,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是农业植保 JSON 修复助手。"
                            "请把输入修复为合法 JSON。"
                            "顶层只保留“用药”和可选“农事建议”。"
                            "所有必填字段必须存在且不能为空。"
                            "“用药.总量”必须是本次作业全田总用量。"
                            "不要输出解释。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"请修复以下内容为合法 JSON：\n{json.dumps(raw, ensure_ascii=False)}",
                    },
                ],
            )
            opinion = self._extract_and_validate(repair_raw)

        if opinion is None:
            raise RuntimeError(f"{config['name']} 输出校验失败")

        return opinion

    async def _invoke_qwen(
        self,
        request_id: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """调用 Qwen API。"""
        url = self._resolve_chat_url(self.api_url)
        response = await self._client.post(
            url,
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

    def _extract_and_validate(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """从 LLM 响应中提取 JSON 并校验 schema。"""
        content = self._extract_content(raw)
        if content is None:
            return None

        # 解析 JSON
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except (json.JSONDecodeError, TypeError):
            return None

        # 清理和规范化
        parsed = self._sanitize(parsed)
        parsed = self._normalize(parsed)

        # 校验
        try:
            validate(instance=parsed, schema=EXPERT_OUTPUT_SCHEMA)
            return parsed
        except ValidationError:
            return None

    @staticmethod
    def _extract_content(raw: dict[str, Any]) -> str | dict | None:
        """从不同格式的 LLM 响应中提取内容。"""
        # OpenAI 格式
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            return choices[0].get("message", {}).get("content")

        # DashScope 格式
        output = raw.get("output", {})
        if isinstance(output, dict) and "text" in output:
            return output["text"]

        # 直接包含用药
        if "用药" in raw:
            return raw

        return None

    @staticmethod
    def _sanitize(payload: dict[str, Any]) -> dict[str, Any]:
        """移除 schema 外的字段。"""
        allowed = {"用药", "农事建议"}
        return {k: v for k, v in payload.items() if k in allowed}

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
        """确保必填字段存在。"""
        med = payload.setdefault("用药", {})
        for key in ("农药名称", "浓度", "配比", "总量", "安全提示"):
            if key not in med:
                if key == "安全提示":
                    med[key] = ["请按说明书使用"]
                else:
                    med[key] = "未知"
        return payload

    @staticmethod
    def _resolve_chat_url(api_url: str) -> str:
        """确保 URL 指向 chat/completions 端点。"""
        if "/chat/completions" in api_url:
            return api_url
        base = api_url.rstrip("/")
        return f"{base}/chat/completions"

    def _publish_event(
        self, request_id: str, event_type: str, message: str, payload: dict,
    ) -> None:
        """发布事件到事件总线。"""
        if self.event_bus is None:
            return
        try:
            self.event_bus.publish(
                request_id=request_id,
                stage="consultation",
                status=event_type,
                message=message,
                payload=payload,
            )
        except Exception:
            pass
