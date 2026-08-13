"""Tests for DecisionRouter."""

from modules.decision.router import DecisionRouter, RoutingSignals


def test_high_scores_route_to_expert():
    """高信号 → 专家模型路径。"""
    router = DecisionRouter(familiarity_threshold=0.6)
    signals = RoutingSignals(
        pesticide_match_count=4,
        historical_case_count=3,
        best_pesticide_score=0.85,
        candidate_pesticide_count=5,
    )
    result = router.route(signals)
    assert result.path == "expert"
    assert result.familiarity_score >= 0.6


def test_low_scores_route_to_multi_agent():
    """低信号 → 多智能体会诊。"""
    router = DecisionRouter(familiarity_threshold=0.6)
    signals = RoutingSignals(
        pesticide_match_count=0,
        historical_case_count=0,
        best_pesticide_score=0.0,
        candidate_pesticide_count=0,
    )
    result = router.route(signals)
    assert result.path == "multi_agent"


def test_zero_signals_always_multi_agent():
    """全零信号 → multi_agent。"""
    router = DecisionRouter()
    result = router.route(RoutingSignals())
    assert result.path == "multi_agent"
    assert result.familiarity_score == 0.0


def test_medium_scores_route_to_multi_agent():
    """中等信号，不够阈值 → multi_agent。"""
    router = DecisionRouter(familiarity_threshold=0.6)
    signals = RoutingSignals(
        pesticide_match_count=1,
        historical_case_count=1,
        best_pesticide_score=0.3,
        candidate_pesticide_count=2,
    )
    result = router.route(signals)
    assert result.path == "multi_agent"


def test_high_score_but_few_pesticides_routes_to_multi_agent():
    """匹配度高但农药匹配数不足 → multi_agent。"""
    router = DecisionRouter(familiarity_threshold=0.6)
    signals = RoutingSignals(
        pesticide_match_count=1,  # < MIN_PESTICIDE_MATCHES=2
        historical_case_count=3,
        best_pesticide_score=0.9,
        candidate_pesticide_count=5,
    )
    result = router.route(signals)
    assert result.path == "multi_agent"


def test_boundary_at_threshold():
    """刚好在阈值边界。"""
    router = DecisionRouter(familiarity_threshold=0.5)
    signals = RoutingSignals(
        pesticide_match_count=3,
        historical_case_count=2,
        best_pesticide_score=0.5,
        candidate_pesticide_count=3,
    )
    result = router.route(signals)
    assert result.path == "expert"
    assert result.familiarity_score >= 0.5
