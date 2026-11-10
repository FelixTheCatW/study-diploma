from __future__ import annotations

import pandas as pd

from src.expert_validation import (
    SAMPLE_COLUMNS,
    build_expert_pack,
    evaluate_expert_labels,
)


def _sample() -> pd.DataFrame:
    rows = []
    for cluster in range(3):
        for index in range(6):
            rows.append(
                {
                    "meal_id": f"m{cluster}_{index}",
                    "cluster": cluster,
                    "cluster_name": f"pattern_{cluster}",
                    "distance": float(index),
                    "id": f"u{cluster}",
                    "date": "2024-01-01",
                    "meal": "breakfast",
                    "products": "egg, rice",
                    "energy_kcal_mean_per_100g": 100.0 + index,
                    "protein_g_mean_per_100kcal": 5.0,
                    "fat_g_mean_per_100kcal": 4.0,
                    "carbohydrates_g_mean_per_100kcal": 10.0,
                    "fiber_g_mean_per_100kcal": 2.0,
                    "sugars_g_mean_per_100kcal": 3.0,
                    "saturated_fat_g_mean_per_100kcal": 1.0,
                    "sodium_mg_mean_per_100kcal": 50.0,
                    "n_products": 2,
                }
            )
    return pd.DataFrame(rows)[
        [
            "meal_id",
            "cluster",
            "cluster_name",
            "distance",
            *[
                column
                for column in SAMPLE_COLUMNS
                if column not in {"sample_id", "meal_id"}
            ],
        ]
    ]


def test_build_pack_hides_cluster_labels(tmp_path):
    paths = build_expert_pack(_sample(), tmp_path, n_per_cluster=6, random_state=42)
    sample = pd.read_csv(paths["sample"])
    key = pd.read_csv(paths["key"])

    assert len(sample) == 18
    assert len(key) == 18
    assert not {"cluster", "distance", "confidence_band"} & set(sample.columns)
    assert key.groupby(["cluster", "confidence_band"]).size().eq(2).all()
    assert not sample["meal_id"].duplicated().any()
    assert key["distance"].map(lambda value: value == round(value, 10)).all()


def test_expert_labels_perfect_agreement(tmp_path):
    paths = build_expert_pack(_sample(), tmp_path, n_per_cluster=6, random_state=42)
    key = pd.read_csv(paths["key"])
    labels = pd.read_csv(paths["template"])
    labels["expert_pattern"] = labels["sample_id"].map(
        key.set_index("sample_id")["cluster_name"]
    )
    labels_path = tmp_path / "filled.csv"
    labels.to_csv(labels_path, index=False)

    summary = evaluate_expert_labels(paths["key"], labels_path, tmp_path / "out")
    assert summary["n_labels"] == 18
    assert summary["raw_agreement"] == 1.0
    assert summary["cohen_kappa"] == 1.0
    assert summary["passes_product"] is True
