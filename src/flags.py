"""Риск-флаги приёма пищи по нутриентной плотности.

Флаги описательные: они сравнивают приём с распределением reference-выборки,
а не с медицинскими нормами. Пропуск нутриента не трактуется как низкое или
высокое значение.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.keys import meal_id_series

FLAG_RULES: dict[str, tuple[str, str, float]] = {
    "high_saturated_fat": ("saturated_fat_g_mean_per_100kcal", "high", 0.75),
    "high_sugars": ("sugars_g_mean_per_100kcal", "high", 0.75),
    "high_sodium": ("sodium_mg_mean_per_100kcal", "high", 0.75),
    "low_fiber": ("fiber_g_mean_per_100kcal", "low", 0.25),
    "low_protein": ("protein_g_mean_per_100kcal", "low", 0.25),
}


def compute_thresholds(meal_table: pd.DataFrame) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    for _, (column, _direction, quantile) in FLAG_RULES.items():
        values = pd.to_numeric(meal_table[column], errors="coerce").dropna()
        if values.empty:
            thresholds[column] = float("nan")
        else:
            thresholds[column] = float(values.quantile(quantile))
    return thresholds


def save_thresholds(thresholds: dict[str, float], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                key: (None if pd.isna(value) else float(value))
                for key, value in thresholds.items()
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_thresholds(path: str | Path) -> dict[str, float]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Пороговые значения флагов не найдены: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    return {
        key: (float("nan") if value is None else float(value))
        for key, value in payload.items()
    }


def flags_from_density(
    values: dict[str, float | None],
    thresholds: dict[str, float],
) -> dict[str, object]:
    """Рассчитать флаги по плотностям на 100 ккал для одного приёма."""
    flags: dict[str, object] = {}
    missing_input = False
    n_flags = 0
    for flag, (column, direction, _) in FLAG_RULES.items():
        value = values.get(column)
        threshold = thresholds.get(column, float("nan"))
        if value is None or pd.isna(value) or pd.isna(threshold):
            flags[flag] = False
            missing_input = True
            continue
        if direction == "high":
            flag_value = float(value) > threshold
        else:
            flag_value = float(value) < threshold
        flags[flag] = bool(flag_value)
        n_flags += int(flag_value)
    flags["missing_input"] = missing_input
    flags["n_flags"] = n_flags
    return flags


def meal_flags(
    meal_table: pd.DataFrame,
    thresholds: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Рассчитать флаги для каждого приёма.

    Возвращаются ключи, флаги и ``missing_input``. Если нужный нутриент
    отсутствует, соответствующий флаг остаётся ``False``, а приём помечается
    как неполный.
    """
    thresholds = thresholds or compute_thresholds(meal_table)
    result = pd.DataFrame(
        {
            "meal_id": meal_id_series(meal_table),
            "id": meal_table["id"],
            "date": meal_table["date"],
            "meal": meal_table["meal"],
        }
    )
    missing_input = pd.Series(False, index=meal_table.index)
    for flag, (column, direction, _) in FLAG_RULES.items():
        values = pd.to_numeric(meal_table[column], errors="coerce")
        threshold = thresholds[column]
        if direction == "high":
            flag_values = values > threshold
        else:
            flag_values = values < threshold
        flag_values = flag_values.fillna(False).astype(bool)
        result[flag] = flag_values.to_numpy()
        missing_input |= values.isna()

    result["missing_input"] = missing_input.to_numpy()
    flag_columns = list(FLAG_RULES)
    result["n_flags"] = result[flag_columns].sum(axis=1).astype(int)
    return result


def cluster_flag_summary(
    flags: pd.DataFrame,
    labels: pd.DataFrame,
) -> pd.DataFrame:
    """Доля приёмов с каждым флагом по кластерам."""
    merged = flags.merge(labels[["meal_id", "cluster"]], on="meal_id", how="inner")
    flag_columns = list(FLAG_RULES)
    summary = (
        merged.groupby("cluster", as_index=False)
        .agg(
            n=("meal_id", "size"),
            missing_input=("missing_input", "mean"),
            **{flag: (flag, "mean") for flag in flag_columns},
        )
        .reset_index(drop=True)
    )
    return summary
