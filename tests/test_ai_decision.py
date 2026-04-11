from __future__ import annotations

import httpx
import pytest

from modules.ai_decision import DecisionEngine, DecisionEngineError


class StubWeatherClient:
    async def fetch_current_weather(self, location_query, request_id, client_ip="127.0.0.1"):
        assert location_query == "上海"
        return {
            "temperature": 27.5,
            "humidity": 58.0,
            "wind_direction": "东南风",
            "wind_scale": 3,
            "wind_scale_text": "3",
            "wind_speed": 2.3,
            "summary": "sunny",
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
            field_context={
                "geofence": [
                    [121.4728, 31.2298],
                    [121.4746, 31.2298],
                    [121.4748, 31.2312],
                ]
            },
            weather_data={
                "temperature": 26,
                "humidity": 58,
                "wind_speed": 3.3,
            },
        )
    finally:
        import asyncio

        asyncio.run(engine.close())

    assert decision["用药"]["农药名称"] == "示范药剂-aphid"
    assert decision["指令"]["飞行路径"][0] == [121.4728, 31.2298]
    assert decision["指令"]["喷洒速率"] == 1.1
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
                              "指令": {
                                "飞行路径": [[121.4729, 31.2300], [121.4740, 31.2308]],
                                "高度": 3.5,
                                "速度": 2.4,
                                "喷洒速率": 1.2,
                                "覆盖区域": {
                                  "type": "polygon",
                                  "coordinates": [[121.4729, 31.2300], [121.4740, 31.2300], [121.4740, 31.2308]]
                                },
                                "气象限制": {
                                  "最大风速": 4.5,
                                  "最低温度": 15,
                                  "最高温度": 33,
                                  "最大湿度": 85
                                }
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
                    "pest_type": "rice-planthopper",
                    "confidence": 0.91,
                    "position": {"x1": 12, "y1": 16, "x2": 32, "y2": 48},
                }
            ],
            field_context={
                "name": "牧野示范田",
                "weather_location": "上海",
                "location": {"city": "上海", "latitude": 31.2304, "longitude": 121.4737},
                "geofence": [
                    [121.4728, 31.2298],
                    [121.4746, 31.2298],
                    [121.4748, 31.2312],
                ],
            },
            request_id="req-ai-1",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"] == "吡虫啉"
    assert result["decision"]["指令"]["喷洒速率"] == 1.2
    assert "害虫检测结果" in result["structured_input_text"]
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
                            "content": '{"用药": {"农药名称": "吡虫啉"}, "指令": {}}'
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
                "weather_location": "上海",
                "location": {"city": "上海", "latitude": 31.2304, "longitude": 121.4737},
                "geofence": [
                    [121.4728, 31.2298],
                    [121.4746, 31.2298],
                    [121.4748, 31.2312],
                ],
            },
            request_id="req-ai-2",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"]
    assert result["decision"]["指令"]["飞行路径"]


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
                              "指令": {
                                "飞行路径": [[121.4729, 31.2300], [121.4740, 31.2308]],
                                "高度": 3.5,
                                "速度": 2.4,
                                "喷洒速率": 1.2,
                                "覆盖区域": {
                                  "type": "polygon",
                                  "coordinates": [[121.4729, 31.2300], [121.4740, 31.2300], [121.4740, 31.2308]]
                                },
                                "气象限制": {
                                  "最大风速": 4.5,
                                  "最低温度": 15,
                                  "最高温度": 33,
                                  "最大湿度": 85
                                }
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
                "weather_location": "上海",
                "location": {"city": "上海", "latitude": 31.2304, "longitude": 121.4737},
                "geofence": [
                    [121.4728, 31.2298],
                    [121.4746, 31.2298],
                    [121.4748, 31.2312],
                ],
            },
            request_id="req-ai-3",
        )
    finally:
        await engine.close()

    assert result["decision"]["用药"]["农药名称"] == "吡虫啉"
