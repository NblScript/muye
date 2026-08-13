"""Tests for ExpertConsultation orchestration."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.decision.agents.consultation import ExpertConsultation
from modules.decision.agents.expert_roles import EXPERT_ROLES


def _make_providers():
    return {
        "qwen": {"api_url": "https://dashscope.example.com/v1", "api_key": "test-qwen", "model": "qwen-max"},
        "deepseek": {"api_url": "https://api.deepseek.com/v1", "api_key": "test-ds", "model": "deepseek-chat"},
        "xiaomi": {"api_url": "https://xiaomi.example.com/v1", "api_key": "test-xm", "model": "xiaomi-model"},
    }


def _make_llm_response(pesticide: str = "吡虫啉", concentration: str = "10% 可湿性粉剂"):
    """构建模拟的 LLM API 响应。"""
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
    return {"name": "展示农田", "area_mu": 10, "crop_name": "小麦", "location": {}}


@pytest.fixture
def consultation():
    """创建测试用的 ExpertConsultation 实例。"""
    return ExpertConsultation(
        providers=_make_providers(),
        rag_retriever=None,
        event_bus=None,
        logger=MagicMock(),
        timeout_seconds=10,
    )


@pytest.mark.asyncio
async def test_consult_all_experts_succeed(consultation):
    """所有专家成功返回意见。"""
    with patch.object(consultation, "_invoke_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_response()

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
    assert mock_llm.call_count == 3  # 3 experts


@pytest.mark.asyncio
async def test_consult_one_expert_fails(consultation):
    """一个专家失败，剩余专家投票。"""
    call_count = 0

    async def mock_invoke(provider, request_id, messages):
        nonlocal call_count
        call_count += 1
        # 第二个专家（农学家）失败
        if call_count == 2:
            raise RuntimeError("API timeout")
        return _make_llm_response()

    with patch.object(consultation, "_invoke_llm", side_effect=mock_invoke):
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
    with patch.object(consultation, "_invoke_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = RuntimeError("API unavailable")

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

    async def mock_invoke(provider, request_id, messages):
        nonlocal call_count
        p = pesticides[call_count % 3]
        call_count += 1
        return _make_llm_response(pesticide=p)

    with patch.object(consultation, "_invoke_llm", side_effect=mock_invoke):
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

    c = ExpertConsultation(
        providers=_make_providers(),
        rag_retriever=None,
        event_bus=mock_bus,
        logger=MagicMock(),
        timeout_seconds=10,
    )

    with patch.object(c, "_invoke_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_response()

        await c.consult(
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


@pytest.mark.asyncio
async def test_expert_uses_correct_provider():
    """验证每个专家使用对应 provider 配置。"""
    c = ExpertConsultation(
        providers=_make_providers(),
        rag_retriever=None,
        event_bus=None,
        logger=MagicMock(),
        timeout_seconds=10,
    )

    captured_providers = []

    async def mock_invoke(provider, request_id, messages):
        captured_providers.append(provider["model"])
        return _make_llm_response()

    with patch.object(c, "_invoke_llm", side_effect=mock_invoke):
        await c.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-006",
        )

    # entomologist→qwen, agronomist→deepseek, pesticide_specialist→xiaomi
    assert captured_providers == ["qwen-max", "deepseek-chat", "xiaomi-model"]


@pytest.mark.asyncio
async def test_invoke_llm_retries_on_server_error(consultation):
    """_invoke_llm 在 5xx 错误时重试。"""
    import httpx

    call_count = 0
    _req = httpx.Request("POST", "https://test.example.com/v1/chat/completions")

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:  # 前两次返回 500
            resp = httpx.Response(500, text="Internal Server Error")
            resp._request = _req
            return resp
        resp = httpx.Response(200, json=_make_llm_response())
        resp._request = _req
        return resp

    consultation._client = MagicMock()
    consultation._client.post = mock_post

    provider = _make_providers()["qwen"]
    result = await consultation._invoke_llm(provider, "test-req", [{"role": "user", "content": "test"}])
    assert call_count == 3  # 2 次失败 + 1 次成功


@pytest.mark.asyncio
async def test_invoke_llm_no_retry_on_client_error(consultation):
    """_invoke_llm 在 4xx 错误时不重试。"""
    import httpx

    call_count = 0
    _req = httpx.Request("POST", "https://test.example.com/v1/chat/completions")

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(429, text="Rate limited")
        resp._request = _req
        return resp

    consultation._client = MagicMock()
    consultation._client.post = mock_post

    provider = _make_providers()["qwen"]
    with pytest.raises(httpx.HTTPStatusError):
        await consultation._invoke_llm(provider, "test-req", [{"role": "user", "content": "test"}])
    assert call_count == 1  # 只调用一次，不重试


@pytest.mark.asyncio
async def test_invoke_llm_retries_on_network_error(consultation):
    """_invoke_llm 在网络错误时重试。"""
    import httpx

    call_count = 0
    _req = httpx.Request("POST", "https://test.example.com/v1/chat/completions")

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:  # 第一次网络错误
            raise httpx.ConnectError("Connection refused")
        resp = httpx.Response(200, json=_make_llm_response())
        resp._request = _req
        return resp

    consultation._client = MagicMock()
    consultation._client.post = mock_post

    provider = _make_providers()["qwen"]
    result = await consultation._invoke_llm(provider, "test-req", [{"role": "user", "content": "test"}])
    assert call_count == 2  # 1 次失败 + 1 次成功


@pytest.mark.asyncio
async def test_invoke_llm_exhausts_retries(consultation):
    """_invoke_llm 重试耗尽后抛出异常。"""
    import httpx

    call_count = 0
    _req = httpx.Request("POST", "https://test.example.com/v1/chat/completions")

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(500, text="Internal Server Error")
        resp._request = _req
        return resp

    consultation._client = MagicMock()
    consultation._client.post = mock_post

    provider = _make_providers()["qwen"]
    with pytest.raises(httpx.HTTPStatusError):
        await consultation._invoke_llm(provider, "test-req", [{"role": "user", "content": "test"}])
    assert call_count == 3  # 1 次初始 + 2 次重试


@pytest.mark.asyncio
async def test_consult_two_experts_fail_one_succeeds(consultation):
    """两个专家失败，一个成功。"""
    call_count = 0

    async def mock_invoke(provider, request_id, messages):
        nonlocal call_count
        call_count += 1
        if call_count in [1, 3]:  # 第1和第3个专家失败
            raise RuntimeError("API timeout")
        return _make_llm_response()

    with patch.object(consultation, "_invoke_llm", side_effect=mock_invoke):
        result = await consultation.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-007",
        )

    assert "用药" in result
    assert result["detail"]["active_count"] == 1
    assert result["agreement"] == "single_expert"


@pytest.mark.asyncio
async def test_consult_with_http_500_error(consultation):
    """HTTP 500 错误被正确处理。"""
    import httpx

    async def mock_invoke(provider, request_id, messages):
        raise httpx.HTTPStatusError(
            "Server Error",
            request=httpx.Request("POST", "https://test.com"),
            response=httpx.Response(500),
        )

    with patch.object(consultation, "_invoke_llm", side_effect=mock_invoke):
        result = await consultation.consult(
            pest_detections=[_make_pest_detection()],
            weather_data=_make_weather(),
            field_context=_make_field_context(),
            request_id="test-req-008",
        )

    assert "用药" in result
    assert result["confidence"] == 0.0
    assert result["agreement"] == "all_failed"
