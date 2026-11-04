"""Подготовка данных DietDiary и USDA.

Реализуются три уровня:
1. Продукт в приёме — исходные нутриенты на 100 г.
2. Приём пищи — средний профиль продукта и полнота нутриентов.
3. День — средний профиль по продуктам дня и число приёмов.

Суммирование концентраций на 100 г по продуктам не выполняется: сумма
растёт с числом продуктов и смешивает паттерн с размером корзины. Вместо
неё используются средние значения и плотность на 100 ккал, а размер
приёма выносится в отдельный признак ``n_products``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import (
    DIARY_CSV,
    MIN_PRODUCTS_WITH_NUTRIENTS,
    NUTRIENT_COLUMNS,
    PROCESSED_DIR,
    resolve_usda_dir,
)
from src.data_loader import DataLoader
from src.utils import add_nutrients, parse_diary, search_products


def _normalize_identifier(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    text = str(value)
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


class DataPreparer:
    """Собрать продуктовую, приёмную и дневную таблицы."""

    def __init__(
        self,
        diary_path: str | Path = DIARY_CSV,
        usda_dir: str | Path | None = None,
        processed_dir: str | Path = PROCESSED_DIR,
        product_table_path: str | Path | None = None,
        meal_table_path: str | Path | None = None,
        day_table_path: str | Path | None = None,
        nutrient_columns: list[str] | None = None,
        min_products_with_nutrients: int = MIN_PRODUCTS_WITH_NUTRIENTS,
    ):
        self.diary_path = Path(diary_path)
        self.usda_dir = Path(usda_dir) if usda_dir is not None else None
        self.processed_dir = Path(processed_dir)
        self.product_table_path = (
            Path(product_table_path)
            if product_table_path is not None
            else self.processed_dir / "product_table.csv"
        )
        self.meal_table_path = (
            Path(meal_table_path)
            if meal_table_path is not None
            else self.processed_dir / "meal_table.csv"
        )
        self.day_table_path = (
            Path(day_table_path)
            if day_table_path is not None
            else self.processed_dir / "day_table.csv"
        )
        self.nutrient_columns = list(nutrient_columns or NUTRIENT_COLUMNS)
        self.min_products_with_nutrients = int(min_products_with_nutrients)

    def _resolve_usda_dir(self) -> Path:
        return self.usda_dir if self.usda_dir is not None else resolve_usda_dir()

    def _normalize_product_table(self, table: pd.DataFrame) -> pd.DataFrame:
        """Привести типы продуктовой таблицы к стабильной схеме.

        CSV не сохраняет pandas-типы, поэтому при чтении кэша даты, строковые
        идентификаторы и флаги восстанавливаются явно.
        """
        table = table.copy()
        if "date" in table.columns:
            table["date"] = pd.to_datetime(table["date"], errors="coerce")
        for column in ("id", "meal", "product", "images", "match_source", "match_name"):
            if column in table.columns:
                table[column] = table[column].astype("string")
        if "fdc_id" in table.columns:
            table["fdc_id"] = table["fdc_id"].map(_normalize_identifier).astype("string")
        if "n_images" in table.columns:
            table["n_images"] = pd.to_numeric(
                table["n_images"], errors="coerce"
            ).astype("Int64")
        if "is_matched" in table.columns:
            table["is_matched"] = table["is_matched"].astype(bool)
        for column in self.nutrient_columns:
            if column in table.columns:
                table[column] = pd.to_numeric(table[column], errors="coerce")
        return table

    def build_final_table(self, force: bool = False) -> pd.DataFrame:
        """Совместимый псевдоним ``build_product_table`` из block07."""
        return self.build_product_table(force=force)

    def build_product_table(self, force: bool = False) -> pd.DataFrame:
        """Построить таблицу «продукт в приёме» и обогатить её USDA.

        Если кэш существует и ``force=False``, таблица загружается с диска.
        """
        if self.product_table_path.exists() and not force:
            table = DataLoader.load_path(self.product_table_path)
            return self._normalize_product_table(table)

        parsed = parse_diary(self.diary_path)
        usda_dir = self._resolve_usda_dir()
        found = search_products(parsed, usda_dir)
        table = add_nutrients(parsed, found, usda_dir)
        table = self._normalize_product_table(table)
        DataLoader.save_dataframe(table, self.product_table_path)
        return table

    def _prepare_quality(self, data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        nutrient_columns = [
            column for column in self.nutrient_columns if column in data.columns
        ]
        if not nutrient_columns:
            raise ValueError(
                "В таблице нет ни одной колонки нутриентов из "
                f"{self.nutrient_columns}"
            )
        prepared = data.copy()
        prepared["_completeness"] = prepared[nutrient_columns].notna().mean(axis=1)
        prepared["_has_nutrients"] = prepared["_completeness"] > 0
        return prepared, nutrient_columns

    def _add_energy_density(
        self,
        table: pd.DataFrame,
        nutrient_columns: list[str],
    ) -> pd.DataFrame:
        energy_column = "energy_kcal_mean_per_100g"
        if energy_column not in table.columns:
            return table

        energy = table[energy_column]
        safe_energy = energy.where(energy > 0)
        for column in nutrient_columns:
            if column == "energy_kcal":
                continue
            mean_column = f"{column}_mean_per_100g"
            if mean_column not in table.columns:
                continue
            table[f"{column}_mean_per_100kcal"] = (
                100 * table[mean_column] / safe_energy
            )
        return table

    def aggregate_by_user_meal(self, product_table: pd.DataFrame) -> pd.DataFrame:
        """Агрегировать продукты до приёма пищи.

        Возвращаются средние нутриенты на 100 г (допущение равной массы
        продуктов), плотность на 100 ккал, полнота нутриентов и число
        продуктов. Сумм нутриентов нет.
        """
        required = {"id", "date", "meal", "product"}
        missing = required - set(product_table.columns)
        if missing:
            raise ValueError(f"В таблице продуктов отсутствуют колонки: {sorted(missing)}")

        data, nutrient_columns = self._prepare_quality(product_table)
        grouped = data.groupby(["id", "date", "meal"], dropna=False)

        summary = grouped.agg(
            n_products=("product", "size"),
            n_products_with_nutrients=("_has_nutrients", "sum"),
            nutrient_completeness=("_completeness", "mean"),
        ).reset_index()

        means = (
            grouped[nutrient_columns]
            .mean()
            .add_suffix("_mean_per_100g")
            .reset_index()
        )
        meal = summary.merge(means, on=["id", "date", "meal"], how="left")
        meal = self._add_energy_density(meal, nutrient_columns)
        meal["is_reliable"] = (
            meal["n_products_with_nutrients"] >= self.min_products_with_nutrients
        )
        return meal.sort_values(["id", "date", "meal"]).reset_index(drop=True)

    def aggregate_by_user_day(self, product_table: pd.DataFrame) -> pd.DataFrame:
        """Агрегировать продукты до дня пользователя.

        Вес и стартовый вес берутся первым значением дня; нутриенты —
        средние по продуктам дня. Сумм нутриентов нет.
        """
        required = {"id", "date", "meal", "product"}
        missing = required - set(product_table.columns)
        if missing:
            raise ValueError(f"В таблице продуктов отсутствуют колонки: {sorted(missing)}")

        data, nutrient_columns = self._prepare_quality(product_table)
        grouped = data.groupby(["id", "date"], dropna=False)

        aggregations: dict[str, tuple[str, str]] = {
            "n_meals": ("meal", "nunique"),
            "n_products": ("product", "size"),
            "n_products_with_nutrients": ("_has_nutrients", "sum"),
            "nutrient_completeness": ("_completeness", "mean"),
        }
        if "start_weight" in data.columns:
            aggregations["start_weight"] = ("start_weight", "first")
        if "weight" in data.columns:
            aggregations["weight"] = ("weight", "first")

        summary = grouped.agg(**aggregations).reset_index()
        means = (
            grouped[nutrient_columns]
            .mean()
            .add_suffix("_mean_per_100g")
            .reset_index()
        )
        day = summary.merge(means, on=["id", "date"], how="left")
        day = self._add_energy_density(day, nutrient_columns)
        day["is_reliable"] = (
            day["n_products_with_nutrients"] >= self.min_products_with_nutrients
        )
        return day.sort_values(["id", "date"]).reset_index(drop=True)

    def prepare(self, force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Построить и сохранить продуктовую, приёмную и дневную таблицы."""
        product = self.build_product_table(force=force)
        meal = self.aggregate_by_user_meal(product)
        day = self.aggregate_by_user_day(product)

        DataLoader.save_dataframe(meal, self.meal_table_path)
        DataLoader.save_dataframe(day, self.day_table_path)
        return product, meal, day

    @staticmethod
    def summary(product: pd.DataFrame, meal: pd.DataFrame, day: pd.DataFrame) -> dict:
        """Краткая сводка подготовленных данных."""
        return {
            "n_products": int(len(product)),
            "n_meals": int(len(meal)),
            "n_days": int(len(day)),
            "n_users": int(product["id"].nunique()) if "id" in product.columns else 0,
            "n_unique_products": int(product["product"].nunique())
            if "product" in product.columns
            else 0,
            "match_coverage": float(product["is_matched"].mean())
            if "is_matched" in product.columns
            else None,
        }
