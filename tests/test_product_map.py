from __future__ import annotations

from src.config import PRODUCT_MAP_PATH
from src.utils import load_product_map


def test_project_product_map_is_complete_and_reviewed():
    table = load_product_map(PRODUCT_MAP_PATH)

    assert len(table) == 197
    assert table["product"].is_unique
    assert table["reviewed"].all()
    assert table["fdc_id"].notna().sum() == 165
    assert table.loc[table["fdc_id"].notna(), "fdc_id"].str.fullmatch(r"\d+").all()
    assert table.loc[table["fdc_id"].isna(), "match_name"].eq("").all()
