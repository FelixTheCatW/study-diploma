from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

_TMP_ROOT = Path(__file__).resolve().parent / ".pytest_tmp"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(_TMP_ROOT)

from src.utils import add_nutrients, parse_diary, search_products


@pytest.fixture()
def diary_frame() -> pd.DataFrame:
    """Мини-дневник: два пользователя, три дня, пять приёмов."""
    return pd.DataFrame(
        {
            "ID": ["u1", "u1", "u2"],
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "breakfast": [
                "b1.jpg;b2.jpg|||chicken rice",
                "|||egg",
                "|||",
            ],
            "lunch": [
                "|||unknown",
                "|||choco",
                "|||rice egg",
            ],
            "supper": ["|||", "|||", "|||"],
            "start_weight": [70.5, 70.0, 60.0],
            "weight": [70.0, 69.8, 59.8],
        }
    )


@pytest.fixture()
def usda_dir(tmp_path):
    """Мини-справочник USDA с generic, branded и category-записями."""
    directory = tmp_path / "usda"
    directory.mkdir()

    foods = pd.DataFrame(
        [
            {
                "fdc_id": "1",
                "data_type": "foundation_food",
                "description": "chicken breast",
                "food_category_id": "1",
            },
            {
                "fdc_id": "2",
                "data_type": "sr_legacy_food",
                "description": "white rice",
                "food_category_id": "2",
            },
            {
                "fdc_id": "3",
                "data_type": "foundation_food",
                "description": "egg",
                "food_category_id": "3",
            },
            {
                "fdc_id": "4",
                "data_type": "branded_food",
                "description": "sweet snack",
                "food_category_id": "4",
            },
            {
                "fdc_id": "5",
                "data_type": "foundation_food",
                "description": "milk",
                "food_category_id": "4",
            },
        ]
    )
    foods.to_csv(directory / "food.csv", index=False)

    branded = pd.DataFrame(
        [
            {
                "fdc_id": "4",
                "short_description": "milk chocolate bar",
                "brand_owner": "Test",
                "branded_food_category": "Snacks",
            }
        ]
    )
    branded.to_csv(directory / "branded_food.csv", index=False)

    categories = pd.DataFrame(
        [
            {"id": "1", "description": "Poultry", "code": "0100"},
            {"id": "2", "description": "Cereals", "code": "0200"},
            {"id": "3", "description": "Eggs", "code": "0300"},
            {"id": "4", "description": "Dairy", "code": "0400"},
        ]
    )
    categories.to_csv(directory / "food_category.csv", index=False)

    nutrients = {
        "1": {
            1008: 165.0,
            1003: 31.0,
            1004: 3.6,
            1005: 0.0,
            1079: 0.0,
            2000: 0.0,
            1258: 1.0,
            1253: 85.0,
            1093: 74.0,
            1092: 256.0,
            1051: 65.0,
        },
        "2": {
            1008: 130.0,
            1003: 2.7,
            1004: 0.3,
            1005: 28.0,
            1079: 0.4,
            2000: 0.1,
            1258: 0.1,
            1253: 0.0,
            1093: 1.0,
            1092: 35.0,
            1051: 68.0,
        },
        "3": {
            1008: 155.0,
            1003: 13.0,
            1004: 11.0,
            1005: 1.1,
            1079: 0.0,
            2000: 1.1,
            1258: 3.3,
            1253: 373.0,
            1093: 124.0,
            1092: 126.0,
            1051: 76.0,
        },
        "4": {
            1008: 535.0,
            1003: 7.6,
            1004: 30.0,
            1005: 59.0,
            1079: 3.4,
            2000: 52.0,
            1258: 18.0,
            1253: 23.0,
            1093: 79.0,
            1092: 559.0,
            1051: 1.5,
        },
        "5": {
            1008: 42.0,
            1003: 3.4,
            1004: 1.0,
            1005: 5.0,
            1079: 0.0,
            2000: 5.0,
            1258: 0.6,
            1253: 5.0,
            1093: 44.0,
            1092: 150.0,
            1051: 89.0,
        },
    }

    records = []
    for fdc_id, values in nutrients.items():
        for nutrient_id, amount in values.items():
            records.append(
                {
                    "fdc_id": fdc_id,
                    "nutrient_id": nutrient_id,
                    "amount": amount,
                }
            )
    pd.DataFrame(records).to_csv(directory / "food_nutrient.csv", index=False)
    return directory


@pytest.fixture()
def product_table(diary_frame: pd.DataFrame, usda_dir) -> pd.DataFrame:
    parsed = parse_diary(diary_frame)
    found = search_products(parsed, usda_dir)
    return add_nutrients(parsed, found, usda_dir)
