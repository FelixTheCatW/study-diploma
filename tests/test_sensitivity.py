from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.datasets import make_blobs

from src.sensitivity import (
    _conclusions,
    _fit_labels,
    _fit_on_all_predict_core,
    _min_cluster_share,
    run_sensitivity,
)


def _blobs() -> pd.DataFrame:
    values, _ = make_blobs(
        n_samples=60,
        centers=3,
        n_features=3,
        cluster_std=0.3,
        random_state=42,
    )
    frame = pd.DataFrame(values, columns=["f1", "f2", "f3"])
    frame["missing_f1"] = 0
    return frame


def test_fit_variant_and_min_share():
    frame = _blobs()
    labels = _fit_labels(
        frame,
        ["f1", "f2", "f3"],
        ["missing_f1"],
        algorithm="kmeans",
        k=3,
        clip=True,
        random_state=42,
    )
    assert len(labels) == len(frame)
    assert 0 < _min_cluster_share(labels) <= 1


def _meal_table() -> pd.DataFrame:
    values, _ = make_blobs(
        n_samples=60,
        centers=3,
        n_features=3,
        cluster_std=0.3,
        random_state=42,
    )
    frame = pd.DataFrame(
        {
            "id": [f"u{index}" for index in range(60)],
            "date": pd.Timestamp("2024-01-01")
            + pd.to_timedelta(np.arange(60), unit="D"),
            "meal": ["breakfast"] * 60,
            "n_products": 2,
            "core_complete": True,
            "energy_kcal_mean_per_100g": 100.0 + np.arange(60),
            "protein_g_mean_per_100g": 5.0 + np.arange(60) * 0.1,
            "fat_g_mean_per_100g": 3.0 + np.arange(60) * 0.05,
            "carbohydrates_g_mean_per_100g": 10.0 + np.arange(60) * 0.2,
            "fiber_g_mean_per_100kcal": 1.0 + values[:, 0],
            "sugars_g_mean_per_100kcal": 3.0 + np.abs(values[:, 1]),
            "saturated_fat_g_mean_per_100kcal": 1.0 + np.abs(values[:, 2]),
            "sodium_mg_mean_per_100kcal": 50.0 + np.arange(60),
            "potassium_mg_mean_per_100kcal": 100.0 + np.arange(60),
            "water_g_mean_per_100kcal": 50.0 + np.arange(60),
        }
    )
    return frame


def test_run_sensitivity_includes_product_variant(tmp_path):
    table = _meal_table()
    products = pd.DataFrame(
        {
            "id": table["id"],
            "date": table["date"],
            "meal": table["meal"],
            "product": "rice",
        }
    )
    products.loc[:9, "product"] = "meal_replacement_powder"
    product_path = tmp_path / "products.csv"
    products.to_csv(product_path, index=False)

    result, metadata = run_sensitivity(
        table,
        k=2,
        random_state=42,
        product_table_path=product_path,
    )

    assert metadata["n_core"] == 60
    assert "no_meal_replacement" in set(result["variant"])
    assert "no_clip" in set(result["variant"])
    assert "relaxed_all_meals" in set(result["variant"])
    assert np.isfinite(result["ari_vs_reference"]).all()
    assert result["min_cluster_share"].between(0, 1).all()

    conclusions = "\n".join(_conclusions(result))
    assert "no_meal_replacement" in conclusions
    assert "no_clip" in conclusions


def test_fit_on_all_predict_core():
    frame = _blobs()
    labels = _fit_on_all_predict_core(
        frame,
        frame,
        ["f1", "f2", "f3"],
        ["missing_f1"],
        k=3,
        random_state=42,
    )
    assert len(labels) == len(frame)
    assert len(np.unique(labels)) == 3
