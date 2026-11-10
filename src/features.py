"""Признаки приёма пищи для кластеризации.

Основная выборка — приёмы с полным покрытием ядра (energy + БЖУ). Доли БЖУ
считаются по массе, нули заменяются перед ILR. Плотности нутриентов считаются
на 100 ккал; пропуски не заполняются здесь, а передаются в Pipeline вместе с
индикаторами.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import CORE_NUTRIENTS, NUTRIENT_COLUMNS

MACRO_NUTRIENTS = ("protein_g", "fat_g", "carbohydrates_g")
DENSITY_NUTRIENTS = (
    "fiber_g",
    "sugars_g",
    "saturated_fat_g",
    "sodium_mg",
    "potassium_mg",
    "water_g",
)
ZERO_REPLACEMENT = 1e-6


@dataclass(frozen=True)
class FeatureTable:
    frame: pd.DataFrame
    continuous_columns: tuple[str, ...]
    indicator_columns: tuple[str, ...]
    n_input: int
    n_dropped: int

    @property
    def feature_columns(self) -> tuple[str, ...]:
        return self.continuous_columns + self.indicator_columns


def _macro_columns() -> list[str]:
    return [f"{nutrient}_mean_per_100g" for nutrient in MACRO_NUTRIENTS]


def _density_columns() -> list[str]:
    return [f"{nutrient}_mean_per_100kcal" for nutrient in DENSITY_NUTRIENTS]


def _replace_zeros(
    shares: pd.DataFrame, delta: float = ZERO_REPLACEMENT
) -> pd.DataFrame:
    values = shares.to_numpy(dtype=float)
    values = np.where(values <= 0, delta, values)
    values = values / values.sum(axis=1, keepdims=True)
    return pd.DataFrame(values, index=shares.index, columns=shares.columns)


def _ilr_features(shares: pd.DataFrame) -> pd.DataFrame:
    protein = shares["protein_g"]
    fat = shares["fat_g"]
    carbohydrates = shares["carbohydrates_g"]
    return pd.DataFrame(
        {
            "ilr_protein_fat_carb": np.sqrt(2.0 / 3.0)
            * np.log(protein / np.sqrt(fat * carbohydrates)),
            "ilr_fat_carb": np.sqrt(0.5) * np.log(fat / carbohydrates),
        },
        index=shares.index,
    )


def build_feature_table(
    meal_table: pd.DataFrame,
    *,
    require_core_complete: bool = True,
) -> FeatureTable:
    """Собрать матрицу признаков из таблицы приёмов.

    Возвращаются ключи, непрерывные признаки и missing-индикаторы плотностей.
    Приёмы без валидного ядра отбрасываются с подсчётом; пропуски плотностей
    остаются ``NaN`` и обрабатываются внутри Pipeline.
    """
    required = set(_macro_columns()) | {
        "energy_kcal_mean_per_100g",
        "n_products",
        "id",
        "date",
        "meal",
    }
    missing = sorted(required - set(meal_table.columns))
    if missing:
        raise ValueError(f"В таблице приёмов отсутствуют колонки: {missing}")

    data = meal_table
    if require_core_complete and "core_complete" in data.columns:
        data = data[data["core_complete"].astype(bool)]
    data = data.reset_index(drop=True)

    n_input = len(data)
    macro_columns = _macro_columns()
    density_columns = _density_columns()

    macros = data[macro_columns].apply(pd.to_numeric, errors="coerce")
    energy = pd.to_numeric(data["energy_kcal_mean_per_100g"], errors="coerce")
    valid = macros.notna().all(axis=1) & (macros.sum(axis=1) > 0)
    valid &= energy.notna() & (energy > 0)

    dropped = int((~valid).sum())
    data = data.loc[valid].reset_index(drop=True)
    macros = macros.loc[valid].reset_index(drop=True)
    energy = energy.loc[valid].reset_index(drop=True)

    shares = macros.div(macros.sum(axis=1), axis=0)
    shares.columns = list(MACRO_NUTRIENTS)
    shares = _replace_zeros(shares)
    ilr = _ilr_features(shares)

    frame = data[["id", "date", "meal", "n_products"]].copy()
    frame["ilr_protein_fat_carb"] = ilr["ilr_protein_fat_carb"]
    frame["ilr_fat_carb"] = ilr["ilr_fat_carb"]
    frame["energy_density"] = energy
    frame["log_n_products"] = np.log1p(data["n_products"].astype(float))

    continuous_columns = [
        "ilr_protein_fat_carb",
        "ilr_fat_carb",
        "energy_density",
        *[f"{nutrient}_density" for nutrient in DENSITY_NUTRIENTS],
        "log_n_products",
    ]
    indicator_columns: list[str] = []

    for nutrient, column in zip(DENSITY_NUTRIENTS, density_columns, strict=True):
        feature = f"{nutrient}_density"
        indicator = f"missing_{feature}"
        frame[feature] = pd.to_numeric(data[column], errors="coerce")
        frame[indicator] = frame[feature].isna()
        indicator_columns.append(indicator)

    finite = np.isfinite(frame[continuous_columns[:3]]).all(axis=1)
    if not finite.all():
        dropped += int((~finite).sum())
        frame = frame.loc[finite].reset_index(drop=True)

    return FeatureTable(
        frame=frame,
        continuous_columns=tuple(continuous_columns),
        indicator_columns=tuple(indicator_columns),
        n_input=n_input,
        n_dropped=dropped,
    )


def feature_matrix(table: FeatureTable) -> pd.DataFrame:
    """Вернуть только признаки без ключей."""
    return table.frame[list(table.feature_columns)].copy()


def available_nutrients() -> tuple[str, ...]:
    """Список исходных нутриентов, участвующих в признаках."""
    return tuple(nutrient for nutrient in NUTRIENT_COLUMNS if nutrient != "energy_kcal")


def core_nutrients() -> tuple[str, ...]:
    """Ядро, по которому определяется полнота приёма."""
    return tuple(CORE_NUTRIENTS)
