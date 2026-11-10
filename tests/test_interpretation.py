from __future__ import annotations

import pandas as pd

from src.interpretation import (
    _cluster_names,
    _cluster_scope,
    _suggest_name,
    _top_features,
)
from src.keys import meal_id_series


def test_suggest_cluster_names_by_profile():
    assert (
        _suggest_name({"energy_density": 1.9, "fiber_g_density": -0.6})
        == "высокоэнергетический белково-жировой"
    )
    assert (
        _suggest_name({"energy_density": -0.8, "fiber_g_density": 1.3})
        == "растительный высококлетчаточный"
    )
    assert (
        _suggest_name({"energy_density": 0.1, "fiber_g_density": 0.1})
        == "смешанный/типичный"
    )


def test_cluster_names_and_top_features():
    profiles = pd.DataFrame(
        [
            {"cluster": 0, "feature": "energy_density", "z_score": 1.9},
            {"cluster": 0, "feature": "fiber_g_density", "z_score": -0.6},
            {"cluster": 1, "feature": "energy_density", "z_score": 0.1},
            {"cluster": 1, "feature": "fiber_g_density", "z_score": 0.1},
            {"cluster": 2, "feature": "energy_density", "z_score": -0.8},
            {"cluster": 2, "feature": "fiber_g_density", "z_score": 1.3},
        ]
    )
    names = _cluster_names(profiles)
    assert names[0].startswith("высокоэнергетический")
    assert names[1] == "смешанный/типичный"
    assert names[2].startswith("растительный")

    top = _top_features(profiles, n=1)
    assert len(top) == 3
    assert set(top["cluster"]) == {0, 1, 2}


def test_cluster_scope_flags_product_specific_and_mixed():
    profiles = pd.DataFrame(
        [
            {"cluster": 0, "feature": "energy_density", "z_score": 1.8},
            {"cluster": 1, "feature": "energy_density", "z_score": 0.1},
            {"cluster": 2, "feature": "fiber_g_density", "z_score": 1.2},
        ]
    )
    products = pd.DataFrame(
        [
            {"cluster": 0, "product": "meal_replacement_powder", "share": 0.67},
            {"cluster": 0, "product": "egg", "share": 0.12},
            {"cluster": 1, "product": "egg", "share": 0.30},
            {"cluster": 2, "product": "cabbage", "share": 0.22},
        ]
    )
    names = {0: "a", 1: "b", 2: "c"}

    scope = _cluster_scope(profiles, products, names)

    assert scope.set_index("cluster").loc[0, "scope"] == "product_specific"
    assert scope.set_index("cluster").loc[1, "scope"] == "mixed"
    assert scope.set_index("cluster").loc[2, "scope"] == "pattern"


def test_meal_id_is_stable():
    frame = pd.DataFrame(
        {
            "id": ["u1"],
            "date": ["2024-01-01"],
            "meal": ["breakfast"],
        }
    )
    assert meal_id_series(frame).iloc[0] == "u1|2024-01-01|breakfast"
