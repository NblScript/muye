from __future__ import annotations

import httpx
import pytest

from modules.decision.ai_decision import DecisionEngine, DecisionEngineError


class StubWeatherClient:
    async def fetch_current_weather(self, location_query, request_id, client_ip="127.0.0.1"):
        assert location_query == "郑州"
        return {
            "temperature": 27.5,
            "humidity": 58.0,
            "wind_direction": "东南风",
            "wind_scale": 3,
            "wind_scale_text": "3",
            "wind_speed": 2.3,
            "summary": "sunny",
        }


class StubDecisionContextProvider:
    def build_context(self, *, request_id, pest_detections, weather_data, field_context):
        assert request_id == "req-ai-context"
        assert pest_detections[0]["pest_type"] == "aphid"
        assert weather_data["temperature"] == 27.5
        assert field_context["name"] == "牧野示范田"
        return {
            "source": "stub",
            "latest_soil_record": {"ph": 6.8, "moisture_percent": 24.0},
            "candidate_pesticides": [{"product_name": "吡虫啉", "dilution_guidance": "1:1200"}],
        }


def test_ai_decision_resolves_dashscope_base_url() -> None:
    engine = DecisionEngine(
        api_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
    )
    try:
        assert (
            engine._resolve_chat_completions_url(engine.api_url)
            == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        )
    finally:
        import asyncio

        asyncio.run(engine.close())


def test_ai_decision_builds_mock_decision() -> None:
    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        use_mock=True,
    )
    try:
        decision = engine._build_mock_decision(
            pest_detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.95,
                    "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                }
            ],
            field_context={"name": "牧野示范田"},
            weather_data={
                "temperature": 26,
                "humidity": 58,
                "wind_speed": 3.3,
                "summary": "多云",
            },
        )
    finally:
        import asyncio

        asyncio.run(engine.close())

    assert decision["用药"]["农药名称"] == "示范药剂-aphid"
    assert decision["用药"]["总量"] == "1.35L"
    assert "优先针对aphid高发区域安排喷洒作业" in decision["农事建议"][0]


@pytest.mark.asyncio
async def test_ai_decision_generates_valid_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "用药": {
                                "农药名称": "吡虫啉",
                                "浓度": "20%",
                                "配比": "1:1200",
                                "总量": "12L",
                                "安全提示": ["作业人员佩戴防护服", "远离水源喷洒"]
                              },
                              "农事建议": ["优先处理高风险区", "作业前核验实时风速"]
                            }
                            """
                        }
                    }
                ]
            },
        )

    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await engine.generate_decision(
            pest_detections=[
                {
                    "pest_type": "rice-planthopper",
                    "confidence": 0.91,
                    "position": {"x1": 12, "y1": 16, "x2": 32, "y2": 48},
                }
            ],
            field_context={
                "name": "牧野示范田",
                "area_mu": 10.0,
                "weather_location": "郑州",
                "location": {"city": "郑州", "latitude": 34.7473, "longitude": 113.6249},
                "geofence": [
                    [113.6241, 34.7467],
                    [113.6257, 34.7467],
                    [113.6257, 34.7479],
                ],
            },
            request_id="req-ai-1",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"] == "吡虫啉"
    assert result["decision"]["农事建议"] == ["优先处理高风险区", "作业前核验实时风速"]
    assert "害虫检测结果" in result["structured_input_text"]
    assert "地块面积：10.0亩" in result["structured_input_text"]
    assert "总量必须是本次作业全田总用量" in result["structured_input_text"]
    assert "风向=东南风" in result["structured_input_text"]
    assert result["weather"]["temperature"] == 27.5


@pytest.mark.asyncio
async def test_ai_decision_repairs_invalid_schema_with_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"用药": {"农药名称": "吡虫啉"}}'
                        }
                    }
                ]
            },
        )

    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await engine.generate_decision(
            pest_detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.95,
                    "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                }
            ],
            field_context={
                "name": "牧野示范田",
                "weather_location": "郑州",
                "location": {"city": "郑州", "latitude": 34.7473, "longitude": 113.6249},
                "geofence": [
                    [113.6241, 34.7467],
                    [113.6257, 34.7467],
                    [113.6257, 34.7479],
                ],
            },
            request_id="req-ai-2",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"]
    assert result["decision"]["用药"]["安全提示"]
    assert result["decision"]["用药"]["总量"].endswith("L")


@pytest.mark.asyncio
async def test_ai_decision_replaces_non_measurable_total_with_area_based_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "用药": {
                                "农药名称": "吡虫啉",
                                "浓度": "20%",
                                "配比": "1:1200",
                                "总量": "适量",
                                "安全提示": ["佩戴口罩"]
                              }
                            }
                            """
                        }
                    }
                ]
            },
        )

    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await engine.generate_decision(
            pest_detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.95,
                    "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                }
            ],
            field_context={
                "name": "牧野示范田",
                "area_mu": 10.0,
                "weather_location": "郑州",
                "location": {"city": "郑州", "latitude": 34.7473, "longitude": 113.6249},
                "geofence": [
                    [113.6241, 34.7467],
                    [113.6257, 34.7467],
                    [113.6257, 34.7479],
                ],
            },
            request_id="req-ai-total-fallback",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"] == "吡虫啉"
    assert result["decision"]["用药"]["总量"] == "1.35L"


@pytest.mark.asyncio
async def test_ai_decision_accepts_extra_top_level_fields_if_core_keys_exist() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "地块名称": "牧野示范田",
                              "实时天气": {"温度": 26},
                              "用药": {
                                "农药名称": "吡虫啉",
                                "浓度": "20%",
                                "配比": "1:1200",
                                "总量": "12L",
                                "安全提示": ["佩戴口罩"]
                              },
                              "农事建议": ["佩戴防护具"]
                            }
                            """
                        }
                    }
                ]
            },
        )

    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await engine.generate_decision(
            pest_detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.95,
                    "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                }
            ],
            field_context={
                "name": "牧野示范田",
                "weather_location": "郑州",
                "location": {"city": "郑州", "latitude": 34.7473, "longitude": 113.6249},
                "geofence": [
                    [113.6241, 34.7467],
                    [113.6257, 34.7467],
                    [113.6257, 34.7479],
                ],
            },
            request_id="req-ai-3",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"] == "吡虫啉"
    assert result["decision"]["农事建议"] == ["佩戴防护具"]


@pytest.mark.asyncio
async def test_ai_decision_includes_optional_decision_context_when_provider_enabled() -> None:
    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        use_mock=True,
        decision_context_provider=StubDecisionContextProvider(),
    )
    try:
        result = await engine.generate_decision(
            pest_detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.95,
                    "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                }
            ],
            field_context={
                "name": "牧野示范田",
                "weather_location": "郑州",
                "location": {"city": "郑州", "latitude": 34.7473, "longitude": 113.6249},
                "geofence": [
                    [113.6241, 34.7467],
                    [113.6257, 34.7467],
                    [113.6257, 34.7479],
                ],
            },
            request_id="req-ai-context",
        )
    finally:
        await engine.close()

    assert result["decision_context"]["source"] == "stub"
    assert "补充决策参考" in result["structured_input_text"]
    assert "吡虫啉" in result["structured_input_text"]


class StubConsultation:
    """Mock consultation that returns a valid decision."""

    async def consult(self, **kwargs):
        return {
            "用药": {
                "农药名称": "氯虫苯甲酰胺",
                "浓度": "20%",
                "配比": "1500倍液",
                "总量": "40mL/亩",
                "安全提示": ["低毒，施药时请佩戴防护装备"],
            },
            "农事建议": ["建议立即施药"],
            "confidence": 1.0,
            "agreement": "unanimous",
            "detail": {
                "experts": {},
                "failed_roles": [],
                "active_count": 3,
                "vote_distribution": {"氯虫苯甲酰胺": 1.0},
            },
        }


class StubRouter:
    """Mock router that always routes to expert."""

    def __init__(self, threshold=0.6):
        self.familiarity_threshold = threshold

    def route(self, signals):
        from modules.decision.router import RoutingDecision
        return RoutingDecision(
            path="expert",
            familiarity_score=0.9,
            reason="test: always expert",
        )


@pytest.mark.asyncio
async def test_expert_path_escalates_to_multi_agent_on_failure() -> None:
    """When expert path fails (HTTP error), escalate to multi-agent consultation."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Return 500 to simulate API failure
        return httpx.Response(500, text="Internal Server Error")

    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        transport=httpx.MockTransport(handler),
        consultation=StubConsultation(),
        router=StubRouter(),
    )
    try:
        result = await engine.generate_decision(
            pest_detections=[
                {"pest_type": "aphid", "confidence": 0.95, "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}
            ],
            field_context={
                "name": "牧野示范田",
                "area_mu": 10.0,
                "weather_location": "郑州",
                "location": {"city": "郑州", "latitude": 34.7473, "longitude": 113.6249},
                "geofence": [[113.6241, 34.7467], [113.6257, 34.7467], [113.6257, 34.7479]],
            },
            request_id="req-escalate",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"] == "氯虫苯甲酰胺"
    assert result["rag_context"]["decision_path"] == "escalated"
    assert result["rag_context"]["familiarity_score"] == 0.9


@pytest.mark.asyncio
async def test_expert_path_raises_when_no_consultation() -> None:
    """When expert path fails and no consultation module, re-raise the error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    engine = DecisionEngine(
        api_url="https://qwen.test/chat",
        api_key="qwen-key",
        model="qwen-max",
        weather_client=StubWeatherClient(),
        transport=httpx.MockTransport(handler),
        consultation=None,  # No consultation module
        router=StubRouter(),
    )
    try:
        with pytest.raises((DecisionEngineError, httpx.HTTPStatusError)):
            await engine.generate_decision(
                pest_detections=[
                    {"pest_type": "aphid", "confidence": 0.95, "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}
                ],
                field_context={
                    "name": "牧野示范田",
                    "area_mu": 10.0,
                    "weather_location": "郑州",
                    "location": {"city": "郑州", "latitude": 34.7473, "longitude": 113.6249},
                    "geofence": [[113.6241, 34.7467], [113.6257, 34.7467], [113.6257, 34.7479]],
                },
                request_id="req-no-consult",
            )
    finally:
        await engine.close()
