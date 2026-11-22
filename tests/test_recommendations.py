from __future__ import annotations

from src.recommendations import recommend, rules_table


def test_recommendations_are_limited_and_prioritized():
    flags = {
        "low_fiber": True,
        "low_protein": True,
        "high_saturated_fat": True,
        "high_sodium": True,
        "high_sugars": True,
    }
    items = recommend(flags)
    actions = [item for item in items if item.kind == "action"]

    assert len(actions) == 3
    assert [item.code for item in actions] == [
        "low_fiber",
        "low_protein",
        "high_saturated_fat",
    ]
    assert len({item.code for item in items}) == len(items)


def test_no_flags_gives_fallback_not_medical_claim():
    items = recommend({}, cluster=1)
    assert [item.code for item in items] == ["no_deviation", "general_balance"]
    assert "медицин" not in items[0].action.lower()

    high_energy = recommend({}, cluster=0)
    assert [item.code for item in high_energy] == [
        "high_energy_density",
        "general_balance",
    ]


def test_product_specific_cluster_adds_warning():
    items = recommend(
        {"high_sodium": True},
        cluster=0,
        cluster_scope="product_specific",
    )
    assert any(item.kind == "warning" for item in items)
    assert any(item.code == "product_specific" for item in items)
    assert any(item.code == "high_sodium" for item in items)


def test_rules_table_is_complete():
    table = rules_table()
    assert set(table["kind"]) == {"action", "warning"}
    assert {
        "low_fiber",
        "low_protein",
        "high_saturated_fat",
        "high_sodium",
        "high_sugars",
        "no_deviation",
        "high_energy_density",
        "general_balance",
        "product_specific",
    } <= set(table["code"])
