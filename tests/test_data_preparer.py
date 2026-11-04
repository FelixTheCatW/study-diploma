from __future__ import annotations

import pandas as pd
import pytest

from src.data_preparer import DataPreparer


@pytest.fixture()
def preparer(tmp_path, diary_frame, usda_dir):
    diary_path = tmp_path / "diet_diary.csv"
    diary_frame.to_csv(diary_path, index=False)
    return DataPreparer(
        diary_path=diary_path,
        usda_dir=usda_dir,
        processed_dir=tmp_path / "processed",
        min_products_with_nutrients=1,
    )


def test_prepare_builds_three_tables(preparer):
    product, meal, day = preparer.prepare(force=True)

    assert len(product) == 7
    assert len(meal) == 5
    assert len(day) == 3
    assert int(product["is_matched"].sum()) == 6
    assert preparer.product_table_path.exists()
    assert preparer.meal_table_path.exists()
    assert preparer.day_table_path.exists()


def test_meal_aggregation_uses_means_not_sums(preparer):
    _, meal, _ = preparer.prepare(force=True)

    assert not any(column.endswith("_sum") for column in meal.columns)

    row = meal[
        (meal["id"] == "u1")
        & (meal["date"] == pd.Timestamp("2024-01-01"))
        & (meal["meal"] == "breakfast")
    ].iloc[0]

    assert row["n_products"] == 2
    assert row["n_products_with_nutrients"] == 2
    assert row["energy_kcal_mean_per_100g"] == pytest.approx(147.5)
    assert row["protein_g_mean_per_100g"] == pytest.approx(16.85)
    assert row["protein_g_mean_per_100kcal"] == pytest.approx(100 * 16.85 / 147.5)


def test_unmatched_product_is_not_zero_filled(preparer):
    _, meal, _ = preparer.prepare(force=True)

    row = meal[
        (meal["id"] == "u1")
        & (meal["date"] == pd.Timestamp("2024-01-01"))
        & (meal["meal"] == "lunch")
    ].iloc[0]

    assert row["n_products"] == 1
    assert row["n_products_with_nutrients"] == 0
    assert pd.isna(row["energy_kcal_mean_per_100g"])
    assert not bool(row["is_reliable"])


def test_day_aggregation_counts_and_weight(preparer):
    _, _, day = preparer.prepare(force=True)

    row = day[
        (day["id"] == "u1") & (day["date"] == pd.Timestamp("2024-01-01"))
    ].iloc[0]

    assert row["n_meals"] == 2
    assert row["n_products"] == 3
    assert row["n_products_with_nutrients"] == 2
    assert row["energy_kcal_mean_per_100g"] == pytest.approx(147.5)
    assert row["weight"] == pytest.approx(70.0)
    assert row["start_weight"] == pytest.approx(70.5)


def test_min_products_controls_reliability(tmp_path, diary_frame, usda_dir):
    diary_path = tmp_path / "diet_diary.csv"
    diary_frame.to_csv(diary_path, index=False)
    preparer = DataPreparer(
        diary_path=diary_path,
        usda_dir=usda_dir,
        processed_dir=tmp_path / "processed",
        min_products_with_nutrients=2,
    )
    _, meal, day = preparer.prepare(force=True)

    breakfast = meal[
        (meal["id"] == "u1")
        & (meal["date"] == pd.Timestamp("2024-01-01"))
        & (meal["meal"] == "breakfast")
    ].iloc[0]
    lunch = meal[
        (meal["id"] == "u1")
        & (meal["date"] == pd.Timestamp("2024-01-01"))
        & (meal["meal"] == "lunch")
    ].iloc[0]
    first_day = day[
        (day["id"] == "u1") & (day["date"] == pd.Timestamp("2024-01-01"))
    ].iloc[0]

    assert bool(breakfast["is_reliable"])
    assert not bool(lunch["is_reliable"])
    assert bool(first_day["is_reliable"])


def test_summary(preparer):
    product, meal, day = preparer.prepare(force=True)
    summary = preparer.summary(product, meal, day)

    assert summary["n_products"] == 7
    assert summary["n_meals"] == 5
    assert summary["n_days"] == 3
    assert summary["n_users"] == 2
    assert summary["n_unique_products"] == 5
    assert summary["match_coverage"] == pytest.approx(6 / 7)


def test_product_table_is_cached(preparer):
    first = preparer.build_product_table(force=True)
    second = preparer.build_product_table(force=False)

    assert preparer.product_table_path.exists()
    pd.testing.assert_frame_equal(first, second)


def test_missing_usda_raises(tmp_path, diary_frame):
    diary_path = tmp_path / "diet_diary.csv"
    diary_frame.to_csv(diary_path, index=False)
    preparer = DataPreparer(
        diary_path=diary_path,
        usda_dir=tmp_path / "missing",
        processed_dir=tmp_path / "processed",
    )

    with pytest.raises(FileNotFoundError, match="Каталог USDA не найден"):
        preparer.build_product_table(force=True)
