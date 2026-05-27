from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from modules.decision.ai_decision import DECISION_SCHEMA

logger = logging.getLogger(__name__)

# 专家角色输出必须符合此 schema，与 DecisionEngine.DECISION_SCHEMA 一致
EXPERT_OUTPUT_SCHEMA: dict[str, Any] = DECISION_SCHEMA

_JSON_FORMAT_RULE = (
    "你必须只输出一个 JSON 对象，不要输出任何其他内容。"
    '格式：{"用药": {"农药名称": "str", "浓度": "str", "配比": "str", "总量": "数字+单位", "安全提示": ["str"]}, "农事建议": ["str"]}'
    "约束：用药必须是对象不能是数组；所有字段不能为空；总量必须是全田总用量（如200mL）；"
    "安全提示和农事建议必须是字符串数组；禁止输出飞控字段。"
)

EXPERT_ROLES: dict[str, dict[str, Any]] = {
    "entomologist": {
        "name": "昆虫学家",
        "weight": 0.4,
        "llm_provider": "qwen",
        "system_prompt": (
            "你是一位资深昆虫学家，专注于农业害虫的识别、习性和危害评估。"
            + _JSON_FORMAT_RULE +
            "请从害虫生物学角度重点分析：害虫种类确认、生活史阶段、危害程度、繁殖趋势，然后给出用药建议。"
        ),
        "retrieval_query_template": "{pest_names} 生活习性 危害特征 繁殖规律 防治",
        "retrieval_focus": "害虫生物学特性",
    },
    "agronomist": {
        "name": "农学家",
        "weight": 0.35,
        "llm_provider": "deepseek",
        "system_prompt": (
            "你是一位资深农学家，专注于作物栽培、环境因素和综合防治策略。"
            + _JSON_FORMAT_RULE +
            "请从农学角度重点分析：当前作物生长阶段、气象条件对施药的影响、综合防治策略，然后给出用药和农事建议。"
        ),
        "retrieval_query_template": "{crop_name} {pest_names} 气象 防治策略 综合管理",
        "retrieval_focus": "作物环境与综合防治",
    },
    "pesticide_specialist": {
        "name": "植保专家",
        "weight": 0.25,
        "llm_provider": "xiaomi",
        "system_prompt": (
            "你是一位植物保护专家，专注于农药选择、用量计算和安全间隔期。"
            + _JSON_FORMAT_RULE +
            "请从植保角度重点分析：农药选择依据、精确用量计算、安全间隔期、抗药性风险，然后给出用药建议和安全提示。"
        ),
        "retrieval_query_template": "{pest_names} 农药 用量 安全间隔期 禁忌 抗药性",
        "retrieval_focus": "农药选择与安全",
    },
}


def get_role_names() -> list[str]:
    return [cfg["name"] for cfg in EXPERT_ROLES.values()]


def get_total_weight() -> float:
    return sum(cfg["weight"] for cfg in EXPERT_ROLES.values())


def load_provider_mapping(config_path: Path | None = None) -> dict[str, str]:
    """从 model_config.yaml 加载 expert→provider 映射。"""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "model_config.yaml"

    if not config_path.exists():
        logger.debug("model_config.yaml 不存在，使用默认 provider 映射")
        return {}

    try:
        from modules.infra.common import load_yaml
        config = load_yaml(config_path)
        mapping = config.get("expert_providers", {})
        if not isinstance(mapping, dict):
            logger.warning("expert_providers 格式错误，应为字典")
            return {}
        return {str(k): str(v) for k, v in mapping.items()}
    except Exception as exc:
        logger.warning("加载 model_config.yaml 失败: %s", exc)
        return {}


def apply_provider_mapping(mapping: dict[str, str]) -> None:
    """覆盖 EXPERT_ROLES 中的 llm_provider 字段。"""
    for role_name, provider in mapping.items():
        if role_name in EXPERT_ROLES:
            old = EXPERT_ROLES[role_name]["llm_provider"]
            EXPERT_ROLES[role_name]["llm_provider"] = provider
            logger.info("角色 %s provider: %s → %s", role_name, old, provider)
        else:
            logger.warning("未知角色名: %s，跳过", role_name)
