"""Анализ табличных данных и профилирование датасетов.

Модуль не заменяет исследовательский ноутбук, но даёт воспроизводимую
сводку: размеры, пропуски, дубликаты, описательные статистики, категории и
предупреждения о константных и высококардинальных колонках.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import NUTRIENT_COLUMNS
from src.data_loader import DataLoader


def _to_python(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, tuple, dict)):
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _format_cell(value: Any) -> str:
    value = _to_python(value)
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value).replace("|", "\\|")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_format_cell(value) for value in row) + " |")
    return "\n".join(lines)


@dataclass
class DatasetProfile:
    """Профиль одного датасета."""

    name: str
    n_rows: int
    n_columns: int
    memory_mb: float
    duplicate_rows: int
    columns: list[dict[str, Any]]
    numeric_summary: pd.DataFrame
    categorical_summary: dict[str, dict[str, int]]
    constant_columns: list[str] = field(default_factory=list)
    high_cardinality_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "n_rows": self.n_rows,
            "n_columns": self.n_columns,
            "memory_mb": self.memory_mb,
            "duplicate_rows": self.duplicate_rows,
            "columns": [
                {key: _to_python(value) for key, value in column.items()}
                for column in self.columns
            ],
            "numeric_summary": {
                str(index): {str(key): _to_python(value) for key, value in row.items()}
                for index, row in self.numeric_summary.iterrows()
            },
            "categorical_summary": self.categorical_summary,
            "constant_columns": self.constant_columns,
            "high_cardinality_columns": self.high_cardinality_columns,
        }

    def to_markdown(self) -> str:
        lines = [
            f"## {self.name}",
            "",
            f"- Строк: {self.n_rows}",
            f"- Колонок: {self.n_columns}",
            f"- Память: {self.memory_mb:.1f} МБ",
            f"- Дубликатов строк: {self.duplicate_rows}",
            "",
            "### Колонки",
            "",
        ]
        rows = [
            [
                column["name"],
                column["dtype"],
                column["n_missing"],
                f"{column['missing_share']:.1%}",
                column["n_unique"],
                column["example"],
            ]
            for column in self.columns
        ]
        lines.append(
            _markdown_table(
                ["Колонка", "Тип", "Пропуски", "Доля", "Уникальных", "Пример"],
                rows,
            )
        )

        if not self.numeric_summary.empty:
            lines.extend(["", "### Числовые признаки", ""])
            numeric = self.numeric_summary.reset_index().rename(
                columns={"index": "column"}
            )
            lines.append(
                _markdown_table(
                    [str(column) for column in numeric.columns],
                    numeric.values.tolist(),
                )
            )

        if self.categorical_summary:
            lines.extend(["", "### Категориальные признаки", ""])
            for column, values in self.categorical_summary.items():
                top = ", ".join(f"{key}: {value}" for key, value in values.items())
                lines.append(f"- `{column}` — {top}")

        warnings: list[str] = []
        if self.constant_columns:
            warnings.append("Константные колонки: " + ", ".join(self.constant_columns))
        if self.high_cardinality_columns:
            warnings.append(
                "Высокая кардинальность: " + ", ".join(self.high_cardinality_columns)
            )
        if warnings:
            lines.extend(["", "### Предупреждения", ""])
            lines.extend(f"- {warning}" for warning in warnings)

        return "\n".join(lines)


class DataAnalyzer:
    """Профилирование датасетов и предметная сводка по дневнику."""

    def profile(self, dataframe: pd.DataFrame, name: str = "dataset") -> DatasetProfile:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("Ожидается pandas.DataFrame")

        n_rows, n_columns = dataframe.shape
        memory_mb = float(dataframe.memory_usage(deep=True).sum() / 1024**2)
        duplicate_rows = int(dataframe.duplicated().sum())

        columns: list[dict[str, Any]] = []
        constant_columns: list[str] = []
        high_cardinality_columns: list[str] = []

        for column in dataframe.columns:
            series = dataframe[column]
            non_null = series.dropna()
            n_unique = int(series.nunique(dropna=True))
            n_missing = int(series.isna().sum())
            columns.append(
                {
                    "name": str(column),
                    "dtype": str(series.dtype),
                    "n_missing": n_missing,
                    "missing_share": n_missing / n_rows if n_rows else 0.0,
                    "n_unique": n_unique,
                    "example": _to_python(non_null.iloc[0])
                    if not non_null.empty
                    else None,
                }
            )
            if series.nunique(dropna=False) <= 1:
                constant_columns.append(str(column))
            if not pd.api.types.is_numeric_dtype(series):
                threshold = max(20, 0.5 * n_rows)
                if n_unique > threshold:
                    high_cardinality_columns.append(str(column))

        numeric = dataframe.select_dtypes(include=[np.number])
        numeric_summary = numeric.describe().T if not numeric.empty else pd.DataFrame()

        categorical_summary: dict[str, dict[str, int]] = {}
        for column in dataframe.select_dtypes(exclude=[np.number]).columns:
            counts = dataframe[column].value_counts(dropna=False).head(5)
            categorical_summary[str(column)] = {
                str(key): int(value) for key, value in counts.items()
            }

        return DatasetProfile(
            name=name,
            n_rows=n_rows,
            n_columns=n_columns,
            memory_mb=memory_mb,
            duplicate_rows=duplicate_rows,
            columns=columns,
            numeric_summary=numeric_summary,
            categorical_summary=categorical_summary,
            constant_columns=constant_columns,
            high_cardinality_columns=high_cardinality_columns,
        )

    def profile_file(
        self,
        path: str | Path,
        name: str | None = None,
        *,
        nrows: int | None = None,
        columns: list[str] | None = None,
    ) -> DatasetProfile:
        dataframe = DataLoader.load_path(path, nrows=nrows, columns=columns)
        return self.profile(dataframe, name or Path(path).stem)

    def diary_summary(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        """Предметная сводка по таблице «продукт в приёме»."""
        summary: dict[str, Any] = {
            "n_products": int(len(dataframe)),
            "n_unique_products": int(dataframe["product"].nunique())
            if "product" in dataframe.columns
            else 0,
        }

        if {"id", "date"} <= set(dataframe.columns):
            summary["n_users"] = int(dataframe["id"].nunique())
            summary["n_days"] = int(len(dataframe[["id", "date"]].drop_duplicates()))

        if {"id", "date", "meal"} <= set(dataframe.columns):
            summary["n_meals"] = int(
                len(dataframe[["id", "date", "meal"]].drop_duplicates())
            )
            meal_slots = dataframe.drop_duplicates(["id", "date", "meal"])
            summary["meal_counts"] = {
                str(key): int(value)
                for key, value in meal_slots["meal"].value_counts().items()
            }
            products_per_meal = (
                dataframe.groupby(["id", "date", "meal"]).size().describe()
            )
            summary["products_per_meal"] = {
                str(key): _to_python(value) for key, value in products_per_meal.items()
            }

        present_nutrients = [
            column for column in NUTRIENT_COLUMNS if column in dataframe.columns
        ]
        if present_nutrients:
            summary["missing_share"] = {
                column: float(dataframe[column].isna().mean())
                for column in present_nutrients
            }

        if "is_matched" in dataframe.columns:
            summary["match_coverage"] = float(dataframe["is_matched"].mean())

        if "energy_kcal" in dataframe.columns:
            energy = pd.to_numeric(dataframe["energy_kcal"], errors="coerce").dropna()
            if not energy.empty:
                q1, q3 = energy.quantile([0.25, 0.75])
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = int(((energy < lower) | (energy > upper)).sum())
                summary["energy_outliers"] = {
                    "count": outliers,
                    "share": outliers / len(energy),
                    "lower": float(lower),
                    "upper": float(upper),
                }

        return summary

    def save_markdown(
        self,
        profiles: dict[str, DatasetProfile],
        path: str | Path,
    ) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        parts = ["# Профиль данных", ""]
        parts.extend(profile.to_markdown() for profile in profiles.values())
        path.write_text("\n\n".join(parts), encoding="utf-8")
        return path
