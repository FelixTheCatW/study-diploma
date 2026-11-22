from __future__ import annotations

import joblib
import pandas as pd
import pytest

from src.clustering import fit_final_pipeline
from src.features import build_feature_table, feature_matrix
from src.flags import compute_thresholds, save_thresholds
from src.inference import ValidationError, infer_meal


def _meals() -> pd.DataFrame:
    rows = []
    for index in range(45):
        group = index % 3
        energy = [60.0, 150.0, 300.0][group]
        protein = 10.0 + group
        fat = 2.0 + group
        carbohydrates = 20.0 - group
        rows.append(
            {
                "id": f"u{index}",
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=index),
                "meal": "lunch",
                "n_products": 2,
                "core_complete": True,
                "energy_kcal_mean_per_100g": energy,
                "protein_g_mean_per_100g": protein,
                "fat_g_mean_per_100g": fat,
                "carbohydrates_g_mean_per_100g": carbohydrates,
                "protein_g_mean_per_100kcal": 100.0 * protein / energy,
                "fat_g_mean_per_100kcal": 100.0 * fat / energy,
                "carbohydrates_g_mean_per_100kcal": 100.0 * carbohydrates / energy,
                "fiber_g_mean_per_100kcal": [5.0, 2.0, 0.5][group],
                "sugars_g_mean_per_100kcal": [2.0, 5.0, 12.0][group],
                "saturated_fat_g_mean_per_100kcal": [0.5, 1.5, 3.0][group],
                "sodium_mg_mean_per_100kcal": [30.0, 100.0, 300.0][group],
                "potassium_mg_mean_per_100kcal": [200.0, 150.0, 100.0][group],
                "water_g_mean_per_100kcal": [80.0, 50.0, 20.0][group],
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture()
def inference_paths(tmp_path):
    meals = _meals()
    features = build_feature_table(meals)
    pipeline, _ = fit_final_pipeline(
        feature_matrix(features),
        features.continuous_columns,
        features.indicator_columns,
        algorithm="kmeans",
        k=3,
        random_state=42,
    )
    model_path = tmp_path / "model.joblib"
    joblib.dump(pipeline, model_path)

    thresholds_path = tmp_path / "thresholds.json"
    save_thresholds(compute_thresholds(meals), thresholds_path)

    scope_path = tmp_path / "scope.csv"
    pd.DataFrame(
        [
            {"cluster": 0, "cluster_name": "plant", "scope": "pattern"},
            {"cluster": 1, "cluster_name": "mixed", "scope": "mixed"},
            {"cluster": 2, "cluster_name": "dense", "scope": "pattern"},
        ]
    ).to_csv(scope_path, index=False)
    return {
        "model_path": model_path,
        "thresholds_path": thresholds_path,
        "scope_path": scope_path,
    }


def test_infer_meal_returns_cluster_flags_and_recommendations(inference_paths):
    result = infer_meal(
        {
            "energy_kcal": 200.0,
            "protein_g": 10.0,
            "fat_g": 5.0,
            "carbohydrates_g": 20.0,
            "fiber_g": 2.0,
            "sugars_g": 3.0,
            "saturated_fat_g": 1.0,
            "cholesterol_mg": 10.0,
            "sodium_mg": 100.0,
            "potassium_mg": 200.0,
            "water_g": 60.0,
        },
        n_products=2,
        **inference_paths,
    )
    assert result.cluster in {0, 1, 2}
    assert result.recommendations
    assert isinstance(result.flags, dict)


def test_infer_meal_allows_missing_optional_nutrients(inference_paths):
    result = infer_meal(
        {
            "energy_kcal": 200.0,
            "protein_g": 10.0,
            "fat_g": 5.0,
            "carbohydrates_g": 20.0,
        },
        n_products=1,
        **inference_paths,
    )
    assert result.recommendations
    assert not any(result.flags.values())
    assert result.missing_input is True
    assert result.n_flags == 0


def test_validation_rejects_bad_core_and_bad_products(inference_paths):
    with pytest.raises(ValidationError, match="energy_kcal"):
        infer_meal(
            {"protein_g": 10.0, "fat_g": 5.0, "carbohydrates_g": 20.0},
            **inference_paths,
        )
    with pytest.raises(ValidationError, match="больше 0"):
        infer_meal(
            {
                "energy_kcal": 0.0,
                "protein_g": 10.0,
                "fat_g": 5.0,
                "carbohydrates_g": 20.0,
            },
            **inference_paths,
        )
    with pytest.raises(ValidationError, match="n_products"):
        infer_meal(
            {
                "energy_kcal": 200.0,
                "protein_g": 10.0,
                "fat_g": 5.0,
                "carbohydrates_g": 20.0,
            },
            n_products=2.5,
            **inference_paths,
        )
    with pytest.raises(ValidationError, match="Неизвестные"):
        infer_meal(
            {
                "energy_kcal": 200.0,
                "protein_g": 10.0,
                "fat_g": 5.0,
                "carbohydrates_g": 20.0,
                "salt": 1.0,
            },
            **inference_paths,
        )


def test_missing_model_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="модель не найдена"):
        infer_meal(
            {
                "energy_kcal": 200.0,
                "protein_g": 10.0,
                "fat_g": 5.0,
                "carbohydrates_g": 20.0,
            },
            model_path=tmp_path / "missing.joblib",
        )
