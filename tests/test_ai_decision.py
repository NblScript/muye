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
async def test_ai_decision_rejects_invalid_schema() -> None:
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
        with pytest.raises(DecisionEngineError):
            await engine.generate_decision(
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
