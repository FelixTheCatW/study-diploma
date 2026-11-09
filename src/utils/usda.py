"""Сопоставление продуктов со справочником USDA FoodData Central.

Модуль реализует три источника матчинга (generic-описания, брендированные
продукты и категории) и обогащение таблицы продукта нутриентами на 100 г.
Для одного продукта выбирается лучший матч: приоритет источника, точное
совпадение названия, затем более короткое название.
"""
from __future__ import annotations

import re
from bisect import bisect_left
from collections.abc import Iterable
from functools import lru_cache
from os import PathLike
from pathlib import Path
from typing import Union

import pandas as pd

DataInput = Union[pd.DataFrame, pd.Series, Iterable[str]]

FOODS_FILE = "food.csv"
FOOD_CATEGORY_FILE = "food_category.csv"
BRANDED_FOOD_FILE = "branded_food.csv"
NUTRIENT_FILE = "food_nutrient.csv"

GENERIC_DATA_TYPES = ("foundation_food", "sr_legacy_food")

NUTRIENT_PRIORITY: dict[str, tuple[int, ...]] = {
    "energy_kcal": (1008, 2047, 2048),
    "protein_g": (1003,),
    "fat_g": (1004, 1085),
    "carbohydrates_g": (1005, 1050),
    "fiber_g": (1079, 2033),
    "sugars_g": (2000, 1063),
    "saturated_fat_g": (1258,),
    "cholesterol_mg": (1253,),
    "sodium_mg": (1093,),
    "potassium_mg": (1092,),
    "water_g": (1051,),
}

NUTRIENTS = {
    nutrient_ids[0]: name for name, nutrient_ids in NUTRIENT_PRIORITY.items()
}

NUTRIENT_ID_MAP = {
    nutrient_id: name
    for name, nutrient_ids in NUTRIENT_PRIORITY.items()
    for nutrient_id in nutrient_ids
}

SOURCE_PRIORITY = {
    "food_description": 0,
    "branded_food": 1,
    "food_category": 2,
}

WORD_RE = re.compile(r"[a-z0-9_]+")

RESULT_COLUMNS = [
    "product",
    "source",
    "match",
    "fdc_id",
    "name",
    "data_type",
    "food_category_id",
    "brand_owner",
    "branded_food_category",
    "code",
]


def _as_path(data_dir: str | PathLike) -> Path:
    return Path(data_dir)


def _normalize(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def _products(products: DataInput) -> list[str]:
    if isinstance(products, pd.DataFrame):
        series = products["product"]
    elif isinstance(products, pd.Series):
        series = products
    else:
        series = pd.Series(list(products))
    return [value for value in (_normalize(item) for item in series.dropna().unique()) if value]


def _match_products(
    tokens: Iterable[str],
    names: pd.Series,
    match: str,
) -> dict[str, list]:
    normalized = names.map(_normalize)

    if match == "substring":
        matches: dict[str, list] = {}
        for token in tokens:
            needle = _normalize(token).replace("_", " ")
            if not needle:
                matches[token] = []
                continue
            mask = normalized.str.contains(needle, regex=False, na=False)
            matches[token] = list(names.index[mask])
        return matches

    word_index: dict[str, list] = {}
    for position, name in normalized.items():
        for word in set(WORD_RE.findall(name)):
            word_index.setdefault(word, []).append(position)

    matches = {}
    if match == "prefix":
        sorted_words = sorted(word_index)
        for token in tokens:
            prefix = _normalize(token)
            positions: list = []
            position = bisect_left(sorted_words, prefix)
            while position < len(sorted_words) and sorted_words[position].startswith(prefix):
                positions.extend(word_index[sorted_words[position]])
                position += 1
            matches[token] = sorted(positions)
    else:
        for token in tokens:
            matches[token] = sorted(word_index.get(_normalize(token), []))
    return matches


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=RESULT_COLUMNS)


class USDAFoodRepository:
    """Ленивый доступ к файлам USDA с кэшированием внутри экземпляра."""

    def __init__(self, data_dir: str | PathLike):
        self.data_dir = _as_path(data_dir)
        if not self.data_dir.is_dir():
            raise FileNotFoundError(f"Каталог USDA не найден: {self.data_dir}")
        self._foods: pd.DataFrame | None = None
        self._branded: pd.DataFrame | None = None
        self._categories: pd.DataFrame | None = None
        self._nutrients: pd.DataFrame | None = None

    def _read_csv(self, filename: str, **kwargs) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Файл USDA не найден: {path}")
        return pd.read_csv(path, **kwargs)

    def foods(self) -> pd.DataFrame:
        """Generic-продукты (foundation_food, sr_legacy_food)."""
        if self._foods is None:
            foods = self._read_csv(
                FOODS_FILE,
                dtype=str,
                usecols=["fdc_id", "data_type", "description", "food_category_id"],
            )
            foods = foods[foods["data_type"].isin(GENERIC_DATA_TYPES)]
            self._foods = foods.reset_index(drop=True)
        return self._foods

    def branded(self) -> pd.DataFrame:
        """Брендированные продукты с коротким описанием для матчинга."""
        if self._branded is None:
            foods = self._read_csv(
                FOODS_FILE,
                dtype=str,
                usecols=["fdc_id", "data_type", "description"],
            )
            foods = foods[foods["data_type"] == "branded_food"]

            branded = self._read_csv(
                BRANDED_FOOD_FILE,
                dtype=str,
                usecols=[
                    "fdc_id",
                    "short_description",
                    "brand_owner",
                    "branded_food_category",
                ],
            )
            branded = foods.merge(branded, on="fdc_id", how="left")
            branded = branded[branded["description"].notna()].copy()
            branded["match_name"] = branded["short_description"].fillna(branded["description"])
            self._branded = branded.reset_index(drop=True)
        return self._branded

    def categories(self) -> pd.DataFrame:
        """Категории продуктов как резервный источник матчинга."""
        if self._categories is None:
            categories = self._read_csv(FOOD_CATEGORY_FILE, dtype=str)
            categories = categories.rename(
                columns={"id": "food_category_id", "description": "name"}
            )
            self._categories = categories.reset_index(drop=True)
        return self._categories

    def nutrients(self) -> pd.DataFrame:
        """Нутриенты на 100 г в широком формате (fdc_id × нутриенты).

        Поддерживаются альтернативные идентификаторы USDA: энергия может быть
        в 1008, 2047 или 2048, сахара — в 2000 или 1063 и т.п. Явные нули
        (``amount == 0``) сохраняются. Отсутствующая строка остаётся ``NaN``:
        это «неизвестно», а не ноль.
        """
        if self._nutrients is None:
            nutrients = self._read_csv(
                NUTRIENT_FILE,
                usecols=["fdc_id", "nutrient_id", "amount"],
                dtype={"fdc_id": str, "nutrient_id": int, "amount": float},
            )
            nutrients = nutrients[
                nutrients["nutrient_id"].isin(NUTRIENT_ID_MAP)
            ].copy()
            nutrients["nutrient"] = nutrients["nutrient_id"].map(NUTRIENT_ID_MAP)
            nutrients["_priority"] = [
                NUTRIENT_PRIORITY[nutrient].index(nutrient_id)
                for nutrient, nutrient_id in zip(
                    nutrients["nutrient"], nutrients["nutrient_id"]
                )
            ]
            nutrients = nutrients.sort_values(
                ["fdc_id", "nutrient", "_priority"]
            ).drop_duplicates(["fdc_id", "nutrient"], keep="first")

            table = (
                nutrients.pivot(
                    index="fdc_id",
                    columns="nutrient",
                    values="amount",
                )
                .reindex(columns=list(NUTRIENTS.values()))
                .reset_index()
            )
            table["fdc_id"] = table["fdc_id"].astype(str)
            self._nutrients = table
        return self._nutrients

    def _search_source(
        self,
        tokens: list[str],
        frame: pd.DataFrame,
        names: pd.Series,
        match: str,
        source: str,
        name_column: str,
    ) -> pd.DataFrame:
        records: list[dict[str, object]] = []
        for token, positions in _match_products(tokens, names, match).items():
            for position in positions:
                row = frame.loc[position]
                records.append(
                    {
                        "product": token,
                        "source": source,
                        "match": match,
                        "fdc_id": row.get("fdc_id"),
                        "name": row.get(name_column),
                        "data_type": row.get("data_type"),
                        "food_category_id": row.get("food_category_id"),
                        "brand_owner": row.get("brand_owner"),
                        "branded_food_category": row.get("branded_food_category"),
                        "code": row.get("code"),
                    }
                )
        return pd.DataFrame.from_records(records, columns=RESULT_COLUMNS)

    def search(self, products: DataInput, match: str = "word") -> pd.DataFrame:
        """Найти продукты во всех источниках USDA.

        Сначала выполняется точный матч по словам, затем подстрочный.
        Найденный продукт исключается из дальнейшего поиска.
        """
        tokens = _products(products)
        if not tokens:
            return _empty()

        modes = [match] if match == "substring" else [match, "substring"]
        sources = [
            ("food_description", self.foods(), self.foods()["description"], "description"),
            ("branded_food", self.branded(), self.branded()["match_name"], "match_name"),
            ("food_category", self.categories(), self.categories()["name"], "name"),
        ]

        frames: list[pd.DataFrame] = []
        remaining = list(tokens)

        for mode in modes:
            for source, frame, names, name_column in sources:
                if not remaining:
                    break
                found = self._search_source(
                    remaining, frame, names, mode, source, name_column
                )
                if not found.empty:
                    frames.append(found)
                    resolved = set(found["product"])
                    remaining = [token for token in remaining if token not in resolved]
            if not remaining:
                break

        combined = pd.concat(frames, ignore_index=True) if frames else _empty()
        if remaining:
            unmatched = pd.DataFrame({"product": remaining})
            combined = pd.concat([combined, unmatched], ignore_index=True)

        return combined[RESULT_COLUMNS].reset_index(drop=True)

    def add_nutrients(
        self,
        parsed: pd.DataFrame,
        found: pd.DataFrame | None,
        best: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Добавить нутриенты USDA к таблице продуктов.

        Для каждого продукта берётся лучший матч. Если передан готовый
        ``best`` (например, из курируемой таблицы), поиск не выполняется.
        Несопоставленные продукты сохраняются с пропущенными нутриентами и
        флагом ``is_matched = False``.
        """
        if best is None:
            if found is None:
                raise ValueError("Нужен либо found, либо best с матчами продуктов")
            best = select_best_matches(found)
        nutrients = self.nutrients()

        table = parsed.merge(best, on="product", how="left")
        table = table.merge(nutrients, on="fdc_id", how="left")
        table["is_matched"] = table["fdc_id"].notna()
        table["fdc_id"] = table["fdc_id"].astype("string")

        for column in NUTRIENTS.values():
            if column in table.columns:
                table[column] = pd.to_numeric(table[column], errors="coerce")
        return table


@lru_cache(maxsize=8)
def _repository(data_dir: str) -> USDAFoodRepository:
    return USDAFoodRepository(Path(data_dir))


def select_best_matches(found: pd.DataFrame) -> pd.DataFrame:
    """Выбрать по одному лучшему матчу на продукт.

    Приоритет: generic-описание, брендированный продукт, категория. Внутри
    источника предпочитается точное совпадение названия, затем короткое.
    """
    columns = ["product", "fdc_id", "match_source", "match_name"]
    if found.empty:
        return pd.DataFrame(columns=columns)

    data = found.dropna(subset=["fdc_id"]).copy()
    if data.empty:
        return pd.DataFrame(columns=columns)

    data["fdc_id"] = data["fdc_id"].astype(str)
    data["_priority"] = data["source"].map(SOURCE_PRIORITY).fillna(99)
    data["_exact"] = (
        data["product"].map(_normalize) == data["name"].map(_normalize)
    ).astype(int)
    data["_length"] = data["name"].map(lambda value: len(str(value)))
    data = data.sort_values(
        ["product", "_priority", "_exact", "_length"],
        ascending=[True, True, False, True],
    )
    best = data.groupby("product", as_index=False).first()
    best = best.rename(columns={"source": "match_source", "name": "match_name"})
    return best[columns]


def search_products(
    products: DataInput,
    data_dir: str | PathLike,
    match: str = "word",
) -> pd.DataFrame:
    """Найти продукты в USDA (обёртка над репозиторием)."""
    return _repository(str(Path(data_dir))).search(products, match=match)


def add_nutrients(
    parsed: pd.DataFrame,
    found: pd.DataFrame | None,
    data_dir: str | PathLike,
    best: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Обогатить таблицу продуктов нутриентами USDA на 100 г."""
    return _repository(str(Path(data_dir))).add_nutrients(parsed, found, best=best)
