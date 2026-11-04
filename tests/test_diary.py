from __future__ import annotations

import pandas as pd
import pytest

from src.utils.diary import parse_diary, split_meal_cell


def test_split_meal_cell_with_images_and_products():
    images, products = split_meal_cell("a.jpg;b.jpg|||chicken rice")

    assert images == ["a.jpg", "b.jpg"]
    assert products == ["chicken", "rice"]


def test_split_meal_cell_empty():
    assert split_meal_cell(None) == ([], [])
    assert split_meal_cell(pd.NA) == ([], [])
    assert split_meal_cell("|||") == ([], [])


def test_parse_diary_shape_and_columns(diary_frame):
    parsed = parse_diary(diary_frame)

    assert len(parsed) == 7
    assert list(parsed.columns) == [
        "id",
        "date",
        "meal",
        "product",
        "start_weight",
        "weight",
        "images",
        "n_images",
    ]
    assert pd.api.types.is_datetime64_any_dtype(parsed["date"])
    assert set(parsed["meal"]) == {"breakfast", "lunch"}
    assert parsed["product"].notna().all()


def test_parse_diary_keeps_images_count(diary_frame):
    parsed = parse_diary(diary_frame)
    breakfast = parsed[
        (parsed["id"] == "u1")
        & (parsed["date"] == pd.Timestamp("2024-01-01"))
        & (parsed["meal"] == "breakfast")
    ]

    assert len(breakfast) == 2
    assert breakfast["n_images"].eq(2).all()
    assert breakfast["images"].eq("b1.jpg;b2.jpg").all()


def test_parse_diary_skips_empty_meals(diary_frame):
    parsed = parse_diary(diary_frame)

    assert "supper" not in set(parsed["meal"])


def test_parse_diary_rejects_missing_columns():
    frame = pd.DataFrame({"ID": ["u1"], "date": ["2024-01-01"]})

    with pytest.raises(ValueError, match="отсутствуют колонки"):
        parse_diary(frame)
