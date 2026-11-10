from __future__ import annotations

import numpy as np
import pandas as pd

from src.features import (
    DENSITY_NUTRIENTS,
    build_feature_table,
    feature_matrix,
)


def _meal_row(
    *,
    meal_id: str,
    protein: float,
    fat: float,
    carbohydrates: float,
    energy: float,
    core_complete: bool,
) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "u1",
        "date": pd.Timestamp("2024-01-01"),
        "meal": meal_id,
        "n_products": 2,
        "energy_kcal_mean_per_100g": energy,
        "protein_g_mean_per_100g": protein,
        "fat_g_mean_per_100g": fat,
        "carbohydrates_g_mean_per_100g": carbohydrates,
        "core_complete": core_complete,
    }
    for index, nutrient in enumerate(DENSITY_NUTRIENTS):
        row[f"{nutrient}_mean_per_100kcal"] = float(index + 1)
    return row


def test_build_feature_table_drops_invalid_and_keeps_missing_flags():
    table = pd.DataFrame(
        [
            _meal_row(
                meal_id="breakfast",
                protein=10.0,
                fat=10.0,
                carbohydrates=10.0,
                energy=200.0,
                core_complete=True,
            ),
            _meal_row(
                meal_id="lunch",
                protein=0.0,
                fat=10.0,
                carbohydrates=20.0,
                energy=300.0,
                core_complete=True,
            ),
            _meal_row(
                meal_id="supper",
                protein=5.0,
                fat=5.0,
                carbohydrates=5.0,
                energy=150.0,
                core_complete=False,
            ),
            _meal_row(
                meal_id="snack",
                protein=5.0,
                fat=5.0,
                carbohydrates=5.0,
                energy=0.0,
                core_complete=True,
            ),
        ]
    )
    table.loc[1, "fiber_g_mean_per_100kcal"] = np.nan

    features = build_feature_table(table)

    assert features.n_input == 3
    assert features.n_dropped == 1
    assert len(features.frame) == 2
    assert not features.frame[list(features.continuous_columns[:3])].isna().any().any()
    assert bool(features.frame.loc[1, "missing_fiber_g_density"])
    assert not bool(features.frame.loc[0, "missing_fiber_g_density"])

    matrix = feature_matrix(features)
    assert list(matrix.columns) == list(features.feature_columns)
    assert (
        np.isfinite(
            matrix[
                [
                    "ilr_protein_fat_carb",
                    "ilr_fat_carb",
                    "energy_density",
                    "log_n_products",
                ]
            ]
        )
        .all()
        .all()
    )
    assert np.isnan(matrix.loc[1, "fiber_g_density"])
