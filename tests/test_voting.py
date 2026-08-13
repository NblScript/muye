"""Tests for weighted voting logic."""

from modules.decision.agents.voting import weighted_vote


def _make_opinion(pesticide: str, concentration: str = "10%", dosage: str = "1:1000",
                  total: str = "50 mL/亩", safety: list[str] | None = None,
                  advice: list[str] | None = None):
    return {
        "用药": {
            "农药名称": pesticide,
            "浓度": concentration,
            "配比": dosage,
            "总量": total,
            "安全提示": safety or ["请按说明书使用"],
        },
        "农事建议": advice if advice is not None else ["注意观察"],
    }


def test_unanimous_agreement():
    opinions = {
        "entomologist": _make_opinion("吡虫啉"),
        "agronomist": _make_opinion("吡虫啉"),
        "pesticide_specialist": _make_opinion("吡虫啉"),
    }
    result = weighted_vote(opinions)
    assert result["用药"]["农药名称"] == "吡虫啉"
    assert result["confidence"] == 1.0
    assert result["agreement"] == "unanimous"


def test_majority_agreement():
    opinions = {
        "entomologist": _make_opinion("吡虫啉"),
        "agronomist": _make_opinion("噻虫嗪"),
        "pesticide_specialist": _make_opinion("吡虫啉"),
    }
    result = weighted_vote(opinions)
    assert result["用药"]["农药名称"] == "吡虫啉"
    assert result["confidence"] == 0.65  # 0.4 + 0.25
    assert result["agreement"] == "majority"


def test_divided_opinions():
    opinions = {
        "entomologist": _make_opinion("吡虫啉"),
        "agronomist": _make_opinion("噻虫嗪"),
        "pesticide_specialist": _make_opinion("阿维菌素"),
    }
    result = weighted_vote(opinions)
    # entomologist has highest weight (0.4) so wins the tie
    assert result["用药"]["农药名称"] == "吡虫啉"
    assert result["agreement"] == "divided"


def test_single_expert():
    opinions = {
        "entomologist": _make_opinion("吡虫啉"),
    }
    result = weighted_vote(opinions)
    assert result["用药"]["农药名称"] == "吡虫啉"
    assert result["agreement"] == "single_expert"


def test_all_failed():
    result = weighted_vote({}, failed_roles=["entomologist", "agronomist", "pesticide_specialist"])
    assert result["confidence"] == 0.0
    assert result["agreement"] == "all_failed"
    assert "用药" in result
    assert "安全提示" in result["用药"]


def test_partial_failure():
    opinions = {
        "entomologist": _make_opinion("吡虫啉"),
        "agronomist": _make_opinion("吡虫啉"),
    }
    result = weighted_vote(opinions, failed_roles=["pesticide_specialist"])
    assert result["用药"]["农药名称"] == "吡虫啉"
    assert result["detail"]["failed_roles"] == ["pesticide_specialist"]


def test_safety_tips_merged():
    opinions = {
        "entomologist": _make_opinion("吡虫啉", safety=["戴手套"]),
        "agronomist": _make_opinion("吡虫啉", safety=["戴口罩"]),
        "pesticide_specialist": _make_opinion("吡虫啉", safety=["戴手套"]),
    }
    result = weighted_vote(opinions)
    tips = result["用药"]["安全提示"]
    assert len(tips) == 2  # deduplicated "戴手套"
    assert any("昆虫学家" in t for t in tips)
    assert any("农学家" in t for t in tips)


def test_advice_merged():
    opinions = {
        "entomologist": _make_opinion("吡虫啉", advice=["建议1"]),
        "agronomist": _make_opinion("吡虫啉", advice=["建议2", "建议1"]),
        "pesticide_specialist": _make_opinion("吡虫啉", advice=[]),
    }
    result = weighted_vote(opinions)
    assert "农事建议" in result
    assert "建议1" in result["农事建议"]
    assert "建议2" in result["农事建议"]
    assert len(result["农事建议"]) == 2  # deduplicated


def test_detail_has_expert_summaries():
    opinions = {
        "entomologist": _make_opinion("吡虫啉"),
        "agronomist": _make_opinion("吡虫啉"),
    }
    result = weighted_vote(opinions)
    assert "experts" in result["detail"]
    assert "entomologist" in result["detail"]["experts"]
    assert result["detail"]["experts"]["entomologist"]["name"] == "昆虫学家"


def test_vote_distribution_in_detail():
    opinions = {
        "entomologist": _make_opinion("吡虫啉"),
        "agronomist": _make_opinion("噻虫嗪"),
        "pesticide_specialist": _make_opinion("吡虫啉"),
    }
    result = weighted_vote(opinions)
    dist = result["detail"]["vote_distribution"]
    assert "吡虫啉" in dist
    assert "噻虫嗪" in dist
