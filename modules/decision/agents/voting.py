from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from modules.decision.agents.expert_roles import EXPERT_ROLES

logger = logging.getLogger(__name__)


def weighted_vote(
    opinions: dict[str, dict[str, Any]],
    failed_roles: list[str] | None = None,
) -> dict[str, Any]:
    """加权投票汇总多个专家意见。

    Args:
        opinions: {role_key: decision_dict}，每个 decision_dict 必须符合 EXPERT_OUTPUT_SCHEMA
        failed_roles: 失败的角色列表（不计入投票权重）

    Returns:
        符合 EXPERT_OUTPUT_SCHEMA 的汇总决策，附带 confidence 和 detail
    """
    failed = set(failed_roles or [])
    active = {k: v for k, v in opinions.items() if k not in failed}

    if not active:
        return {
            "用药": {
                "农药名称": "吡虫啉",
                "浓度": "10% 可湿性粉剂",
                "配比": "1:1000",
                "总量": "50 mL/亩",
                "安全提示": ["所有专家调用失败，使用默认建议", "请人工复核"],
            },
            "农事建议": ["建议联系植保站获取专业指导"],
            "confidence": 0.0,
            "agreement": "all_failed",
            "detail": {"failed_roles": list(failed), "active_count": 0},
        }

    # 1. 加权投票农药名称
    pesticide_votes: Counter[str] = Counter()
    for role, opinion in active.items():
        weight = EXPERT_ROLES[role]["weight"]
        name = opinion.get("用药", {}).get("农药名称", "")
        if name:
            pesticide_votes[name] += weight

    final_pesticide = pesticide_votes.most_common(1)[0][0] if pesticide_votes else "未知"

    # 归一化投票分布到 0-1 范围（用于前端柱状图）
    total_vote_weight = sum(pesticide_votes.values()) or 1.0
    normalized_votes = {name: round(w / total_vote_weight, 2) for name, w in pesticide_votes.items()}

    # 2. 选取最终用药方案：优先采纳推荐农药与投票结果一致的专家方案
    best_opinion: dict[str, Any] | None = None
    best_weight = 0.0
    for role, opinion in active.items():
        if opinion.get("用药", {}).get("农药名称") == final_pesticide:
            w = EXPERT_ROLES[role]["weight"]
            if w > best_weight:
                best_weight = w
                best_opinion = opinion

    if best_opinion is None:
        best_opinion = next(iter(active.values()))

    # 3. 构建最终决策
    base_medication = dict(best_opinion.get("用药", {}))
    base_medication["农药名称"] = final_pesticide

    # 4. 合并所有安全提示（去重）
    all_safety: list[str] = []
    seen_safety: set[str] = set()
    for role, opinion in active.items():
        for tip in opinion.get("用药", {}).get("安全提示", []):
            if tip not in seen_safety:
                seen_safety.add(tip)
                all_safety.append(f"[{EXPERT_ROLES[role]['name']}] {tip}")
    base_medication["安全提示"] = all_safety or ["请注意安全使用农药"]

    # 5. 合并农事建议（去重）
    all_advice: list[str] = []
    seen_advice: set[str] = set()
    for role, opinion in active.items():
        for advice in opinion.get("农事建议", []):
            if advice not in seen_advice:
                seen_advice.add(advice)
                all_advice.append(advice)

    # 6. 计算一致性置信度
    confidence = _calculate_confidence(active, final_pesticide)
    agreement = _classify_agreement(active, final_pesticide, confidence)

    # 7. 记录每个专家的意见摘要
    expert_summaries = {}
    for role, opinion in active.items():
        med = opinion.get("用药", {})
        expert_summaries[role] = {
            "name": EXPERT_ROLES[role]["name"],
            "weight": EXPERT_ROLES[role]["weight"],
            "农药名称": med.get("农药名称", ""),
            "总量": med.get("总量", ""),
        }

    result: dict[str, Any] = {
        "用药": base_medication,
    }
    if all_advice:
        result["农事建议"] = all_advice

    result["confidence"] = round(confidence, 2)
    result["agreement"] = agreement
    result["detail"] = {
        "experts": expert_summaries,
        "failed_roles": list(failed),
        "active_count": len(active),
        "vote_distribution": normalized_votes,
    }

    return result


def _calculate_confidence(active: dict[str, dict], final_pesticide: str) -> float:
    """计算专家一致性置信度（0-1）。"""
    if not active:
        return 0.0

    total_weight = 0.0
    agree_weight = 0.0
    for role, opinion in active.items():
        w = EXPERT_ROLES[role]["weight"]
        total_weight += w
        if opinion.get("用药", {}).get("农药名称") == final_pesticide:
            agree_weight += w

    if total_weight == 0:
        return 0.0
    return agree_weight / total_weight


def _classify_agreement(
    active: dict[str, dict], final_pesticide: str, confidence: float
) -> str:
    """分类专家意见一致性级别。"""
    if len(active) == 1:
        return "single_expert"
    if confidence >= 0.9:
        return "unanimous"
    if confidence >= 0.6:
        return "majority"
    return "divided"
