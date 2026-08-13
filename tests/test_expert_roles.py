"""Tests for expert role definitions."""

from modules.decision.agents.expert_roles import EXPERT_ROLES, get_role_names, get_total_weight


def test_three_roles_defined():
    assert set(EXPERT_ROLES.keys()) == {"entomologist", "agronomist", "pesticide_specialist"}


def test_each_role_has_required_fields():
    for role, config in EXPERT_ROLES.items():
        assert "name" in config, f"{role} missing name"
        assert "weight" in config, f"{role} missing weight"
        assert "system_prompt" in config, f"{role} missing system_prompt"
        assert "retrieval_query_template" in config, f"{role} missing retrieval_query_template"
        assert "retrieval_focus" in config, f"{role} missing retrieval_focus"
        assert config["weight"] > 0, f"{role} weight must be positive"
        assert len(config["system_prompt"]) > 50, f"{role} system_prompt too short"


def test_weights_sum_to_one():
    total = get_total_weight()
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected ~1.0"


def test_role_names_are_chinese():
    names = get_role_names()
    assert len(names) == 3
    for name in names:
        assert len(name) > 1
        assert any("一" <= c <= "鿿" for c in name), f"'{name}' has no Chinese chars"


def test_system_prompts_mention_json():
    for role, config in EXPERT_ROLES.items():
        assert "JSON" in config["system_prompt"] or "json" in config["system_prompt"], \
            f"{role} system_prompt should mention JSON"


def test_system_prompts_forbid_flight_fields():
    for role, config in EXPERT_ROLES.items():
        assert "飞控" in config["system_prompt"] or "飞行" in config["system_prompt"], \
            f"{role} system_prompt should forbid flight fields"


def test_retrieval_templates_have_placeholders():
    for role, config in EXPERT_ROLES.items():
        template = config["retrieval_query_template"]
        assert "{pest_names}" in template, f"{role} template missing {{pest_names}}"
