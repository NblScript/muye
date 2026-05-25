from __future__ import annotations

from typing import Any

# 专家角色输出必须符合此 schema，与 DecisionEngine.DECISION_SCHEMA 一致
EXPERT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["用药"],
    "additionalProperties": False,
    "properties": {
        "用药": {
            "type": "object",
            "required": ["农药名称", "浓度", "配比", "总量", "安全提示"],
            "additionalProperties": False,
            "properties": {
                "农药名称": {"type": "string", "minLength": 1},
                "浓度": {"type": "string", "minLength": 1},
                "配比": {"type": "string", "minLength": 1},
                "总量": {"type": "string", "minLength": 1},
                "安全提示": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "农事建议": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
}

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
