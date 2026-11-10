"""Курируемое сопоставление продуктов DietDiary с USDA FoodData Central.

Автоматический поиск по короткому названию ошибается на общих словах:
``corn`` может стать ``Oil, corn``, ``egg`` — ``Bread, egg``. Поэтому для
197 продуктов проекта используется ручная таблица. Продукты с неоднозначным
названием намеренно остаются без матча: лучше ``NaN``, чем неверный профиль.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path

import pandas as pd

MAP_COLUMNS = (
    "product",
    "fdc_id",
    "match_name",
    "data_type",
    "notes",
    "reviewed",
)
BEST_COLUMNS = ("product", "fdc_id", "match_source", "match_name", "reviewed", "notes")


def normalize_product(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def _products(products: object) -> list[str]:
    if isinstance(products, pd.DataFrame):
        series = products["product"]
    elif isinstance(products, pd.Series):
        series = products
    else:
        series = pd.Series(list(products))  # type: ignore[arg-type]
    return [
        product
        for product in (normalize_product(item) for item in series.dropna().unique())
        if product
    ]


def load_product_map(path: str | PathLike) -> pd.DataFrame:
    """Загрузить и проверить курируемую таблицу продукт → ``fdc_id``."""
    map_path = Path(path)
    if not map_path.exists():
        raise FileNotFoundError(
            f"Таблица сопоставления продуктов не найдена: {map_path}"
        )

    table = pd.read_csv(map_path, dtype=str, keep_default_na=False)
    missing = [column for column in MAP_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(f"В таблице сопоставления отсутствуют колонки: {missing}")

    table = table.copy()
    table["product"] = table["product"].map(normalize_product)
    table["fdc_id"] = table["fdc_id"].str.strip()
    table.loc[table["fdc_id"] == "", "fdc_id"] = pd.NA
    table["reviewed"] = (
        table["reviewed"].str.strip().str.lower().isin({"true", "1", "yes", "да"})
    )

    duplicates = table.loc[table["product"].duplicated(), "product"].tolist()
    if duplicates:
        raise ValueError(f"Дубликаты продуктов в таблице сопоставления: {duplicates}")
    return table


def curated_best_matches(
    products: object,
    map_path: str | PathLike,
) -> pd.DataFrame:
    """Вернуть матчи из курируемой таблицы без автоматического fallback.

    Для продукта вне таблицы возвращается строка с ``fdc_id = NA`` и
    ``match_source = "unmapped"``. Нутриенты такого продукта останутся
    пропущенными, а не нулевыми.
    """
    tokens = _products(products)
    mapping = load_product_map(map_path)
    mapping = mapping[mapping["product"].isin(tokens)].copy()

    present = set(mapping["product"])
    unmapped = pd.DataFrame(
        {
            "product": [token for token in tokens if token not in present],
            "fdc_id": pd.NA,
            "match_name": pd.NA,
            "data_type": pd.NA,
            "notes": "нет в курируемой таблице",
            "reviewed": False,
        }
    )
    combined = pd.concat([mapping, unmapped], ignore_index=True)
    combined["match_source"] = combined["fdc_id"].map(
        lambda value: "curated_map" if pd.notna(value) else "unmapped"
    )
    combined = combined.sort_values("product").reset_index(drop=True)
    return combined[list(BEST_COLUMNS)]
