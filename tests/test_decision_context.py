from __future__ import annotations

from modules.decision_context import SqliteDecisionContextProvider
from modules.sqlite_store import SqliteStore


def test_sqlite_decision_context_provider_builds_context_from_imported_data(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    try:
        store.upsert_field(
            {
                "field_id": "henan-zz-001",
                "field_code": "HENAN-ZZ-001",
                "field_name": "郑州示范田",
                "province": "河南省",
                "city": "郑州市",
                "county": "中牟县",
                "latitude": 34.74,
                "longitude": 113.62,
                "area_mu": 36,
                "soil_type": "壤土",
            }
        )
        store.upsert_crop_catalog_record(
            {
                "crop_code": "wheat",
                "crop_name": "小麦",
                "category": "粮食作物",
            }
        )
        store.upsert_field_crop_cycle(
            {
                "field_id": "henan-zz-001",
                "crop_code": "wheat",
                "year": 2026,
                "season": "spring",
                "planting_date": "2026-03-01",
                "status": "growing",
                "area_mu": 36,
            }
        )
        store.upsert_soil_record(
            {
                "field_id": "henan-zz-001",
                "sample_date": "2026-04-10",
                "depth_cm": 20,
                "ph": 6.7,
                "moisture_percent": 22.5,
                "organic_matter_gkg": 18.2,
            }
        )
        store.upsert_weather_history_daily(
            {
                "field_id": "henan-zz-001",
                "station_code": "zz001",
                "station_name": "郑州站",
                "observation_date": "2026-04-15",
                "weather_summary": "晴",
                "temperature_avg_c": 24.6,
                "humidity_avg_percent": 55.0,
                "wind_speed_avg_mps": 2.8,
            }
        )
        store.upsert_pesticide_catalog_record(
            {
                "pesticide_id": "p-001",
                "product_name": "吡虫啉",
                "target_crops": ["小麦", "玉米"],
                "target_pests": ["aphid", "蚜虫"],
                "dilution_guidance": "1:1200",
            }
        )

        provider = SqliteDecisionContextProvider(store)
        context = provider.build_context(
            request_id="req-sqlite-context",
            pest_detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.94,
                    "position": {"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                }
            ],
            weather_data={"temperature": 25},
            field_context={
                "field_id": "henan-zz-001",
                "name": "郑州示范田",
                "crop_cycle": {"crop_name": "小麦"},
            },
        )
    finally:
        store.close()

    assert context["source"] == "sqlite"
    assert context["field_profile"]["crop_name"] == "小麦"
    assert context["latest_soil_record"]["ph"] == 6.7
    assert context["recent_weather_history"][0]["weather_summary"] == "晴"
    assert context["candidate_pesticides"][0]["product_name"] == "吡虫啉"
