from __future__ import annotations

import pandas as pd
import pytest

from src.utils import add_nutrients, parse_diary, search_products, select_best_matches
from src.utils.usda import NUTRIENTS, USDAFoodRepository


def test_search_products_uses_generic_branded_and_category(usda_dir):
    found = search_products(["chicken", "choco", "poultry"], usda_dir)
    by_product = found.groupby("product")["source"].apply(set).to_dict()

    assert "food_description" in by_product["chicken"]
    assert "branded_food" in by_product["choco"]
    assert "food_category" in by_product["poultry"]


def test_category_match_has_no_fdc_id(usda_dir):
    found = search_products(["poultry"], usda_dir)
    poultry = found[found["product"] == "poultry"]

    assert not poultry.empty
    assert poultry["fdc_id"].isna().all()
    assert poultry["name"].eq("Poultry").any()


def test_select_best_matches_returns_one_row_per_product(usda_dir):
    found = search_products(["chicken", "choco", "poultry"], usda_dir)
    best = select_best_matches(found)

    assert set(best["product"]) == {"chicken", "choco"}
    assert len(best) == best["product"].nunique()
    assert best.loc[best["product"] == "chicken", "fdc_id"].iloc[0] == "1"
    assert best.loc[best["product"] == "choco", "fdc_id"].iloc[0] == "4"


def test_add_nutrients_merges_values_and_flags_unmatched(usda_dir):
    parsed = pd.DataFrame(
        {
            "id": ["u1", "u1"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "meal": ["breakfast", "breakfast"],
            "product": ["chicken", "unknown"],
        }
    )
    found = search_products(parsed, usda_dir)
    table = add_nutrients(parsed, found, usda_dir)

    chicken = table[table["product"] == "chicken"].iloc[0]
    unknown = table[table["product"] == "unknown"].iloc[0]

    assert chicken["is_matched"]
    assert chicken["energy_kcal"] == 165.0
    assert chicken["protein_g"] == 31.0
    assert not unknown["is_matched"]
    assert pd.isna(unknown["energy_kcal"])
    assert table["fdc_id"].dtype.name == "string"


def test_repository_returns_all_nutrient_columns(usda_dir):
    repository = USDAFoodRepository(usda_dir)
    nutrients = repository.nutrients()

    assert set(NUTRIENTS.values()) <= set(nutrients.columns)
    assert pd.api.types.is_string_dtype(nutrients["fdc_id"])


def test_missing_usda_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="Каталог USDA не найден"):
        search_products(["chicken"], tmp_path / "missing")


def test_parse_then_enrich_keeps_all_products(usda_dir, diary_frame):
    parsed = parse_diary(diary_frame)
    found = search_products(parsed, usda_dir)
    table = add_nutrients(parsed, found, usda_dir)

    assert len(table) == len(parsed)
    assert table["is_matched"].sum() == 6
    assert table["product"].eq("unknown").any()
