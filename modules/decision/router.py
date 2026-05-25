"""Decision Router: 根据知识库匹配度选择专家模型路径或多智能体会诊路径。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RoutingSignals:
    """路由决策信号。"""

    pesticide_match_count: int = 0
    historical_case_count: int = 0
    best_pesticide_score: float = 0.0
    candidate_pesticide_count: int = 0


@dataclass
class RoutingDecision:
    """路由决策结果。"""

    path: str  # "expert" | "multi_agent"
    familiarity_score: float
    reason: str


# 归一化常量
_PESTICIDE_K = 5
_CASE_K = 3
_CANDIDATE_K = 5

# 权重
_W_PESTICIDE = 0.40
_W_CASE = 0.25
_W_SCORE = 0.20
_W_CANDIDATE = 0.15

_MIN_PESTICIDE_MATCHES = 2


class DecisionRouter:
    """根据知识库匹配度决定走专家模型还是多智能体会诊。"""

    def __init__(self, familiarity_threshold: float = 0.6) -> None:
        self.familiarity_threshold = familiarity_threshold

    def route(self, signals: RoutingSignals) -> RoutingDecision:
        score = self._compute_familiarity(signals)

        if (
            score >= self.familiarity_threshold
            and signals.pesticide_match_count >= _MIN_PESTICIDE_MATCHES
        ):
            return RoutingDecision(
                path="expert",
                familiarity_score=round(score, 2),
                reason=(
                    f"已知组合（匹配度 {score:.0%}，"
                    f"农药 {signals.pesticide_match_count} 条，"
                    f"案例 {signals.historical_case_count} 条）"
                ),
            )

        return RoutingDecision(
            path="multi_agent",
            familiarity_score=round(score, 2),
            reason=(
                f"需要会诊（匹配度 {score:.0%}，"
                f"农药 {signals.pesticide_match_count} 条，"
                f"案例 {signals.historical_case_count} 条）"
            ),
        )

    def _compute_familiarity(self, s: RoutingSignals) -> float:
        pesticide_norm = min(s.pesticide_match_count / _PESTICIDE_K, 1.0)
        case_norm = min(s.historical_case_count / _CASE_K, 1.0)
        candidate_norm = min(s.candidate_pesticide_count / _CANDIDATE_K, 1.0)

        return (
            _W_PESTICIDE * pesticide_norm
            + _W_CASE * case_norm
            + _W_SCORE * s.best_pesticide_score
            + _W_CANDIDATE * candidate_norm
        )
