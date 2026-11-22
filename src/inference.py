"""Инференс одного приёма по сырым нутриентам.

Вход: 10 нутриентов на 100 г + n_products. Ядро (energy, protein, fat,
carbohydrates) обязательно; остальные нутриенты могут отсутствовать и
обрабатываются как NaN, а не как ноль.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.config import BASE_DIR, REPORTS_DIR
from src.features import build_feature_table, feature_matrix
from src.flags import flags_from_density, load_thresholds
from src.recommendations import recommend

NUTRIENT_FIELDS = (
    "energy_kcal",
    "protein_g",
    "fat_g",
    "carbohydrates_g",
    "fiber_g",
    "sugars_g",
    "saturated_fat_g",
    "cholesterol_mg",
    "sodium_mg",
    "potassium_mg",
    "water_g",
)
CORE_FIELDS = ("energy_kcal", "protein_g", "fat_g", "carbohydrates_g")
DENSITY_FIELDS = (
    "fiber_g",
    "sugars_g",
    "saturated_fat_g",
    "sodium_mg",
    "potassium_mg",
    "water_g",
)
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "clustering_pipeline.joblib"
DEFAULT_THRESHOLDS_PATH = REPORTS_DIR / "recommendations" / "flag_thresholds.json"
DEFAULT_SCOPE_PATH = REPORTS_DIR / "interpretation" / "cluster_scope.csv"

MAX_VALUES = {
    "energy_kcal": 900.0,
    "protein_g": 100.0,
    "fat_g": 100.0,
    "carbohydrates_g": 100.0,
    "fiber_g": 100.0,
    "sugars_g": 100.0,
    "saturated_fat_g": 100.0,
    "cholesterol_mg": 10000.0,
    "sodium_mg": 100000.0,
    "potassium_mg": 100000.0,
    "water_g": 100.0,
}


class ValidationError(ValueError):
    """Ошибка входных данных."""


@dataclass(frozen=True)
class InferenceResult:
    cluster: int
    cluster_name: str
    cluster_scope: str | None
    flags: dict[str, bool]
    missing_input: bool
    n_flags: int
    recommendations: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


def validate_nutrients(values: dict[str, Any]) -> tuple[dict[str, float | None], int]:
    unknown = sorted(set(values) - set(NUTRIENT_FIELDS) - {"n_products"})
    if unknown:
        raise ValidationError(f"Неизвестные поля: {unknown}")

    result: dict[str, float | None] = {}
    errors: list[str] = []
    for field in NUTRIENT_FIELDS:
        raw = values.get(field)
        if raw is None or raw == "":
            result[field] = None
            if field in CORE_FIELDS:
                errors.append(f"{field}: обязательное поле")
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError):
            errors.append(f"{field}: ожидается число")
            result[field] = None
            continue
        if not math.isfinite(number):
            errors.append(f"{field}: NaN или бесконечность")
            result[field] = None
            continue
        if number < 0:
            errors.append(f"{field}: отрицательное значение")
            result[field] = None
            continue
        if number > MAX_VALUES[field]:
            errors.append(f"{field}: значение больше {MAX_VALUES[field]}")
            result[field] = None
            continue
        result[field] = number

    if result["energy_kcal"] is not None and result["energy_kcal"] <= 0:
        errors.append("energy_kcal: должно быть больше 0")
    n_products = values.get("n_products", 1)
    try:
        n_products_float = float(n_products)
        if not n_products_float.is_integer():
            raise ValueError
        n_products_int = int(n_products_float)
    except (TypeError, ValueError):
        errors.append("n_products: ожидается целое число")
        n_products_int = 1
    if n_products_int < 1 or n_products_int > 50:
        errors.append("n_products: допустимо от 1 до 50")

    if errors:
        raise ValidationError("; ".join(errors))
    return result, n_products_int


def _feature_row(values: dict[str, float | None], n_products: int) -> pd.DataFrame:
    energy = float(values["energy_kcal"])
    row: dict[str, Any] = {
        "id": "input",
        "date": pd.Timestamp("2000-01-01"),
        "meal": "input",
        "n_products": n_products,
        "core_complete": True,
        "energy_kcal_mean_per_100g": energy,
        "protein_g_mean_per_100g": float(values["protein_g"]),
        "fat_g_mean_per_100g": float(values["fat_g"]),
        "carbohydrates_g_mean_per_100g": float(values["carbohydrates_g"]),
    }
    for nutrient in DENSITY_FIELDS:
        value = values[nutrient]
        row[f"{nutrient}_mean_per_100kcal"] = (
            None if value is None else 100.0 * float(value) / energy
        )
    return pd.DataFrame([row])


def _load_scope(path: Path) -> dict[int, dict[str, str]]:
    if not path.exists():
        return {}
    table = pd.read_csv(path)
    if "cluster" not in table.columns:
        return {}
    result: dict[int, dict[str, str]] = {}
    for row in table.to_dict(orient="records"):
        result[int(row["cluster"])] = {
            "name": str(row.get("cluster_name", f"cluster {row['cluster']}")),
            "scope": str(row.get("scope", "")) or None,
        }
    return result


def infer_meal(
    nutrients: dict[str, Any],
    *,
    n_products: int = 1,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    thresholds_path: str | Path = DEFAULT_THRESHOLDS_PATH,
    scope_path: str | Path = DEFAULT_SCOPE_PATH,
) -> InferenceResult:
    values, n_products_value = validate_nutrients(
        {**nutrients, "n_products": n_products}
    )
    model_file = Path(model_path)
    if not model_file.exists():
        raise FileNotFoundError(
            f"Сохранённая модель не найдена: {model_file}. "
            "Сначала выполните python -m src.cluster."
        )
    pipeline = joblib.load(model_file)
    if not hasattr(pipeline, "predict"):
        raise ValueError("Загруженный объект не поддерживает predict()")

    features = build_feature_table(_feature_row(values, n_products_value))
    if len(features.frame) != 1:
        raise ValidationError("Не удалось построить признаки: проверьте ядро приёма")
    matrix = feature_matrix(features)
    cluster = int(pipeline.predict(matrix)[0])

    scope_data = _load_scope(Path(scope_path)).get(cluster, {})
    cluster_name = scope_data.get("name", f"cluster {cluster}")
    cluster_scope = scope_data.get("scope")

    thresholds = load_thresholds(thresholds_path)
    density_values = {
        f"{nutrient}_mean_per_100kcal": (
            None
            if values[nutrient] is None
            else 100.0 * float(values[nutrient]) / float(values["energy_kcal"])
        )
        for nutrient in DENSITY_FIELDS
    }
    flags = flags_from_density(density_values, thresholds)
    recommendations = recommend(
        flags,
        cluster=cluster,
        cluster_scope=cluster_scope,
    )
    actions = [asdict(item) for item in recommendations if item.kind == "action"]
    warnings = [asdict(item) for item in recommendations if item.kind == "warning"]
    flags_bool = {
        key: bool(value)
        for key, value in flags.items()
        if key not in {"missing_input", "n_flags"}
    }
    return InferenceResult(
        cluster=cluster,
        cluster_name=cluster_name,
        cluster_scope=cluster_scope,
        flags=flags_bool,
        missing_input=bool(flags.get("missing_input", False)),
        n_flags=int(flags.get("n_flags", 0)),
        recommendations=actions,
        warnings=warnings,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Инференс одного приёма по сырым нутриентам"
    )
    for field in NUTRIENT_FIELDS:
        parser.add_argument(f"--{field.replace('_', '-')}", type=float, default=None)
    parser.add_argument("--n-products", type=int, default=1)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--scope", type=Path, default=DEFAULT_SCOPE_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    values = {
        field: getattr(args, field)
        for field in NUTRIENT_FIELDS
        if getattr(args, field) is not None
    }
    try:
        result = infer_meal(
            values,
            n_products=args.n_products,
            model_path=args.model,
            thresholds_path=args.thresholds,
            scope_path=args.scope,
        )
    except (ValidationError, FileNotFoundError, ValueError) as exc:
        print(f"Ошибка: {exc}")
        return 1
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
