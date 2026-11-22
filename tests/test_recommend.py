from __future__ import annotations

import pandas as pd

from src.recommend import build_recommendations


def _nutrients() -> dict[str, float]:
    return {
        "protein_g_mean_per_100kcal": 5.0,
        "fiber_g_mean_per_100kcal": 1.0,
        "sugars_g_mean_per_100kcal": 10.0,
        "saturated_fat_g_mean_per_100kcal": 4.0,
        "sodium_mg_mean_per_100kcal": 300.0,
    }


def test_build_recommendations_writes_artifacts(tmp_path):
    meal_rows = []
    for index in range(6):
        row = {
            "id": f"u{index}",
            "date": "2024-01-01",
            "meal": "lunch",
            "core_complete": True,
        }
        row.update(_nutrients())
        row["fiber_g_mean_per_100kcal"] = float(index)
        meal_rows.append(row)
    meal_table = pd.DataFrame(meal_rows)
    meal_path = tmp_path / "meal_table.csv"
    meal_table.to_csv(meal_path, index=False)

    examples = meal_table.head(2).copy()
    examples["meal_id"] = [f"u{index}|2024-01-01|lunch" for index in range(2)]
    examples["cluster"] = 0
    examples["cluster_name"] = "dense"
    examples["example_type"] = "nearest_centroid"
    examples["products"] = "egg, rice"
    examples["energy_density"] = 100.0
    examples["n_products"] = 2
    examples_path = tmp_path / "examples.csv"
    examples.to_csv(examples_path, index=False)

    flags = pd.DataFrame(
        [
            {
                "cluster": 0,
                "n": 2,
                "missing_input": 0.0,
                "high_saturated_fat": 0.8,
                "high_sugars": 0.2,
                "high_sodium": 0.9,
                "low_fiber": 0.7,
                "low_protein": 0.1,
            }
        ]
    )
    flags_path = tmp_path / "flags.csv"
    flags.to_csv(flags_path, index=False)

    scope = pd.DataFrame(
        [
            {
                "cluster": 0,
                "cluster_name": "dense",
                "scope": "product_specific",
                "top_product": "meal_replacement_powder",
                "top_product_share": 0.7,
                "max_abs_z": 1.5,
            }
        ]
    )
    scope_path = tmp_path / "scope.csv"
    scope.to_csv(scope_path, index=False)

    paths = build_recommendations(
        meal_table_path=meal_path,
        examples_path=examples_path,
        cluster_flags_path=flags_path,
        scope_path=scope_path,
        reports_dir=tmp_path / "reports",
    )

    assert paths["report"].exists()
    assert paths["thresholds"].exists()
    result = pd.read_csv(paths["examples"])
    assert result["meal"].eq("lunch").all()
    assert result["recommendation_1"].notna().all()
    assert result["warnings"].str.contains("Кластер 0").any()
