from __future__ import annotations

from modules.decision.compliance import PesticideComplianceChecker


def _rag_context_for_imidacloprid() -> dict:
    return {
        "pesticides": [
            {
                "content": "农药名称：吡虫啉\n适用作物：冬小麦、水稻\n防治对象：蚜虫、飞虱\n毒性：低毒",
                "score": 0.92,
                "metadata": {
                    "product_name": "吡虫啉",
                    "target_crops": ["冬小麦", "水稻"],
                    "target_pests": ["蚜虫", "飞虱"],
                    "toxicity": "低毒",
                    "source": "pesticide_catalog",
                },
            }
        ],
        "crop_name": "小麦",
        "pest_types": ["aphid"],
    }


def test_compliance_passes_when_rag_candidate_matches_crop_and_pest() -> None:
    checker = PesticideComplianceChecker()

    result = checker.check(
        decision={"用药": {"农药名称": "吡虫啉"}},
        rag_context=_rag_context_for_imidacloprid(),
        field_context={"crop_cycle": {"crop_name": "小麦"}},
        pest_detections=[{"pest_type": "aphid", "confidence": 0.91}],
        weather={"wind_speed": 3.2, "humidity": 62},
    )

    assert result["status"] == "passed"
    assert result["score"] == 100
    assert [item["rule"] for item in result["checks"]] == [
        "source_match",
        "crop_match",
        "pest_match",
        "toxicity_risk",
        "weather_risk",
    ]
    assert result["blocking_reasons"] == []
    assert result["warnings"] == []


def test_compliance_blocks_when_crop_or_pest_do_not_match_candidate() -> None:
    checker = PesticideComplianceChecker()
    rag_context = _rag_context_for_imidacloprid()

    result = checker.check(
        decision={"用药": {"农药名称": "吡虫啉"}},
        rag_context=rag_context,
        field_context={"crop_cycle": {"crop_name": "玉米"}},
        pest_detections=[{"pest_type": "corn-borer", "confidence": 0.88}],
        weather={"wind_speed": 2.0, "humidity": 60},
    )

    assert result["status"] == "blocked"
    assert "当前作物玉米不在吡虫啉适用作物范围内" in result["blocking_reasons"]
    assert "检测害虫与吡虫啉防治对象不匹配" in result["blocking_reasons"]


def test_compliance_warns_for_medium_toxicity_and_marginal_weather() -> None:
    checker = PesticideComplianceChecker()
    rag_context = {
        "pesticides": [
            {
                "content": "农药名称：高效氯氟氰菊酯\n适用作物：冬小麦\n防治对象：蚜虫\n毒性：中等毒",
                "score": 0.81,
                "metadata": {
                    "product_name": "高效氯氟氰菊酯",
                    "target_crops": "冬小麦",
                    "target_pests": "蚜虫",
                    "toxicity": "中等毒",
                },
            }
        ],
        "crop_name": "冬小麦",
        "pest_types": ["aphid"],
    }

    result = checker.check(
        decision={"用药": {"农药名称": "高效氯氟氰菊酯"}},
        rag_context=rag_context,
        field_context={"crop_cycle": {"crop_name": "冬小麦"}},
        pest_detections=[{"pest_type": "aphid", "confidence": 0.8}],
        weather={"wind_speed": 6.1, "humidity": 88},
    )

    assert result["status"] == "warning"
    assert result["blocking_reasons"] == []
    assert "高效氯氟氰菊酯毒性为中等毒，执行前需要人工复核" in result["warnings"]
    assert "当前风速6.1m/s偏高，注意药液漂移风险" in result["warnings"]
    assert "当前湿度88%偏高，建议避开降雨或露水窗口" in result["warnings"]


def test_compliance_includes_summary_and_execution_policy() -> None:
    checker = PesticideComplianceChecker()

    # passed
    result = checker.check(
        decision={"用药": {"农药名称": "吡虫啉"}},
        rag_context=_rag_context_for_imidacloprid(),
        field_context={"crop_cycle": {"crop_name": "小麦"}},
        pest_detections=[{"pest_type": "aphid", "confidence": 0.9}],
        weather={"wind_speed": 2.0, "humidity": 55},
    )
    assert "通过全部合规检查" in result["summary"]
    assert result["execution_policy"]["takeoff_mode"] == "auto"

    # blocked
    result_blocked = checker.check(
        decision={"用药": {"农药名称": "吡虫啉"}},
        rag_context=_rag_context_for_imidacloprid(),
        field_context={"crop_cycle": {"crop_name": "玉米"}},
        pest_detections=[{"pest_type": "corn-borer", "confidence": 0.9}],
        weather={"wind_speed": 2.0, "humidity": 55},
    )
    assert "已拦截" in result_blocked["summary"]
    assert result_blocked["execution_policy"]["takeoff_mode"] == "blocked"

    # warning
    rag_warn = {
        "pesticides": [
            {
                "content": "农药名称：高效氯氟氰菊酯\n适用作物：冬小麦\n防治对象：蚜虫\n毒性：中等毒",
                "metadata": {
                    "product_name": "高效氯氟氰菊酯",
                    "target_crops": "冬小麦",
                    "target_pests": "蚜虫",
                    "toxicity": "中等毒",
                },
            }
        ],
    }
    result_warn = checker.check(
        decision={"用药": {"农药名称": "高效氯氟氰菊酯"}},
        rag_context=rag_warn,
        field_context={"crop_cycle": {"crop_name": "冬小麦"}},
        pest_detections=[{"pest_type": "aphid", "confidence": 0.8}],
        weather={"wind_speed": 2.0, "humidity": 55},
    )
    assert "风险提示" in result_warn["summary"]
    assert result_warn["execution_policy"]["takeoff_mode"] == "manual"


def test_compliance_includes_evidence_per_check() -> None:
    checker = PesticideComplianceChecker()

    result = checker.check(
        decision={"用药": {"农药名称": "吡虫啉"}},
        rag_context=_rag_context_for_imidacloprid(),
        field_context={"crop_cycle": {"crop_name": "小麦"}},
        pest_detections=[{"pest_type": "aphid", "confidence": 0.9}],
        weather={"wind_speed": 3.0, "humidity": 60},
    )

    # Every check has an evidence list
    for check in result["checks"]:
        assert "evidence" in check
        assert isinstance(check["evidence"], list)

    # source_match should have evidence from RAG candidate
    source_check = next(c for c in result["checks"] if c["rule"] == "source_match")
    assert len(source_check["evidence"]) > 0
    assert source_check["evidence"][0]["source"] == "pesticide_catalog"
    assert "product_name" in source_check["evidence"][0]["matched_fields"]

    # crop_match evidence
    crop_check = next(c for c in result["checks"] if c["rule"] == "crop_match")
    assert len(crop_check["evidence"]) > 0
    assert "target_crops" in crop_check["evidence"][0]["matched_fields"]

    # weather_risk evidence
    weather_check = next(c for c in result["checks"] if c["rule"] == "weather_risk")
    assert len(weather_check["evidence"]) > 0
    assert weather_check["evidence"][0]["source"] == "weather_api"


def test_compliance_returns_empty_alternatives() -> None:
    checker = PesticideComplianceChecker()

    result = checker.check(
        decision={"用药": {"农药名称": "吡虫啉"}},
        rag_context=_rag_context_for_imidacloprid(),
        field_context={"crop_cycle": {"crop_name": "小麦"}},
        pest_detections=[{"pest_type": "aphid", "confidence": 0.9}],
        weather={"wind_speed": 3.0, "humidity": 60},
    )

    assert result["alternatives"] == []
