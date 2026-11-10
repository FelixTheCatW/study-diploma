from __future__ import annotations

import pandas as pd
import pytest

from src.flags import cluster_flag_summary, compute_thresholds, meal_flags
from src.keys import meal_id_series


def _meal_table() -> pd.DataFrame:
    rows = []
    for index in range(20):
        rows.append(
            {
                "id": f"u{index % 2}",
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=index),
                "meal": "breakfast" if index % 2 == 0 else "lunch",
                "protein_g_mean_per_100kcal": float(index),
                "fiber_g_mean_per_100kcal": float(index),
                "sugars_g_mean_per_100kcal": 100.0 + index,
                "saturated_fat_g_mean_per_100kcal": 10.0 + index,
                "sodium_mg_mean_per_100kcal": 200.0 + index,
            }
        )
    return pd.DataFrame(rows)


def test_thresholds_and_flags():
    table = _meal_table()
    thresholds = compute_thresholds(table)

    assert thresholds["protein_g_mean_per_100kcal"] == pytest.approx(4.75)
    assert thresholds["sugars_g_mean_per_100kcal"] == pytest.approx(114.25)

    flags = meal_flags(table, thresholds)
    assert flags["high_sugars"].sum() == 5
    assert flags["high_sodium"].sum() == 5
    assert flags["low_fiber"].sum() == 5
    assert flags["low_protein"].sum() == 5
    assert not flags["missing_input"].any()


def test_missing_nutrient_is_not_flagged_as_low():
    table = _meal_table()
    table.loc[0, "fiber_g_mean_per_100kcal"] = pd.NA
    table.loc[0, "protein_g_mean_per_100kcal"] = 10.0
    flags = meal_flags(table)

    assert bool(flags.loc[0, "missing_input"])
    assert not bool(flags.loc[0, "low_fiber"])
    assert flags.loc[0, "n_flags"] == 0


def test_cluster_flag_summary_sums_to_cluster_sizes():
    table = _meal_table()
    flags = meal_flags(table)
    labels = pd.DataFrame(
        {
            "meal_id": meal_id_series(table),
            "cluster": [0] * 10 + [1] * 10,
        }
    )
    summary = cluster_flag_summary(flags, labels)

    assert summary["n"].sum() == len(table)
    assert set(summary["cluster"]) == {0, 1}
    assert summary["high_sugars"].between(0, 1).all()
