"""Tests for ExpertConsultation orchestration."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.decision.agents.consultation import ExpertConsultation
from modules.decision.agents.expert_roles import EXPERT_ROLES


def _make_qwen_response(pesticide: str = "吡虫啉", concentration: str = "10% 可湿性粉剂"):
    """构建模拟的 Qwen API 响应。"""
    decision = {
        "用药": {
            "农药名称": pesticide,
            "浓度": concentration,
            "配比": "1:1000",
            "总量": "50 mL/亩",
            "安全提示": ["请按说明书使用"],
        },
        "农事建议": ["注意观察害虫变化"],
    }
    return {
        "choices": [
            {"message": {"content": json.dumps(decision, ensure_ascii=False)}}
        ]
    }


def _make_pest_detection(pest_type: str = "aphid", confidence: float = 0.92):
    return {"pest_type": pest_type, "confidence": confidence}


def _make_weather():
    return {"temperature": 28, "humidity": 75, "weather_desc": "多云"}


def _make_field_context():
    return {"name": "演示农田", "area_mu": 10, "crop_name": "小麦", "location": {}}


@pytest.fixture
def consultation():
    """创建测试用的 ExpertConsultation 实例。"""
    return ExpertConsultation(
        api_url="https://dashscope.example.com/v1",
        api_key="test-key",
        model="qwen-max",
        rag_retriever=None,
        event_bus=None,
        logger=MagicMock(),
        timeout_seconds=10,
    )


@pytest.mark.asyncio
async def test_consult_all_experts_succeed(consultation):
    """所有专家成功返回意见。"""
    with patch.object(consultation, "_invoke_qwen", new_callable=AsyncMock) as mock_qwen:
        mock_qwen.return_value = _make_qwen_response()

        result = await consultation.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-001",
        )

    assert "用药" in result
    assert result["用药"]["农药名称"] == "吡虫啉"
    assert result["confidence"] == 1.0
    assert result["agreement"] == "unanimous"
    assert mock_qwen.call_count == 3  # 3 experts


@pytest.mark.asyncio
async def test_consult_one_expert_fails(consultation):
    """一个专家失败，剩余专家投票。"""
    call_count = 0

    async def mock_invoke(request_id, messages):
        nonlocal call_count
        call_count += 1
        # 第二个专家（农学家）失败
        if call_count == 2:
            raise RuntimeError("API timeout")
        return _make_qwen_response()

    with patch.object(consultation, "_invoke_qwen", side_effect=mock_invoke):
        result = await consultation.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-002",
        )

    assert "用药" in result
    assert result["detail"]["failed_roles"] == ["agronomist"]
    assert result["detail"]["active_count"] == 2


@pytest.mark.asyncio
async def test_consult_all_experts_fail(consultation):
    """所有专家失败时返回默认建议。"""
    with patch.object(consultation, "_invoke_qwen", new_callable=AsyncMock) as mock_qwen:
        mock_qwen.side_effect = RuntimeError("API unavailable")

        result = await consultation.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-003",
        )

    assert "用药" in result
    assert result["confidence"] == 0.0
    assert result["agreement"] == "all_failed"


@pytest.mark.asyncio
async def test_consult_experts_disagree(consultation):
    """专家意见不一致时走投票。"""
    call_count = 0
    pesticides = ["吡虫啉", "噻虫嗪", "阿维菌素"]

    async def mock_invoke(request_id, messages):
        nonlocal call_count
        p = pesticides[call_count % 3]
        call_count += 1
        return _make_qwen_response(pesticide=p)

    with patch.object(consultation, "_invoke_qwen", side_effect=mock_invoke):
        result = await consultation.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-004",
        )

    assert result["agreement"] == "divided"
    assert result["confidence"] < 1.0


@pytest.mark.asyncio
async def test_consult_with_event_bus():
    """验证事件总线收到会诊事件。"""
    mock_bus = MagicMock()

    consultation = ExpertConsultation(
        api_url="https://dashscope.example.com/v1",
        api_key="test-key",
        model="qwen-max",
        rag_retriever=None,
        event_bus=mock_bus,
        logger=MagicMock(),
        timeout_seconds=10,
    )

    with patch.object(consultation, "_invoke_qwen", new_callable=AsyncMock) as mock_qwen:
        mock_qwen.return_value = _make_qwen_response()

        await consultation.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-005",
        )

    # 应该发布: started + 3 expert_opinion + completed = 5 个事件
    assert mock_bus.publish.call_count >= 5

    event_types = [call.kwargs.get("status") or call.args[2] for call in mock_bus.publish.call_args_list]
    assert "consultation_started" in event_types
    assert "consultation_completed" in event_types


def test_resolve_chat_url():
    assert "/chat/completions" in ExpertConsultation._resolve_chat_url("https://api.example.com/v1")
    assert "/chat/completions" in ExpertConsultation._resolve_chat_url(
        "https://api.example.com/v1/chat/completions"
    )
