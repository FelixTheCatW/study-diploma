"""Конфигурация проекта.

Пути к данным, перечень нутриентов, уровни агрегации и правила
разрешения справочника USDA FoodData Central.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = BASE_DIR / "reports"

DIARY_CSV = DATA_DIR / "diet_diary.csv"
FOOD_DATA_CSV = DATA_DIR / "food_data.csv"
HEALTH_FITNESS_CSV = DATA_DIR / "health_fitness_dataset.csv"
FITNESS_TRACKER_CSV = DATA_DIR / "fitness_tracker_dataset.csv"
DAILY_NUTRITION_CSV = DATA_DIR / "daily_nutrition.csv"
MFP_DIARIES_PARQUET = DATA_DIR / "mfp-diaries.parquet"

DATASETS: dict[str, Path] = {
    "diet_diary": DIARY_CSV,
    "health_fitness": HEALTH_FITNESS_CSV,
    "fitness_tracker": FITNESS_TRACKER_CSV,
    "daily_nutrition": DAILY_NUTRITION_CSV,
    "food_data": FOOD_DATA_CSV,
    "mfp_diaries": MFP_DIARIES_PARQUET,
}

PRODUCT_TABLE_PATH = PROCESSED_DIR / "product_table.csv"
MEAL_TABLE_PATH = PROCESSED_DIR / "meal_table.csv"
DAY_TABLE_PATH = PROCESSED_DIR / "day_table.csv"
DATA_PROFILE_PATH = REPORTS_DIR / "data_profile.md"

MEAL_COLUMNS = ("breakfast", "lunch", "supper")

NUTRIENT_COLUMNS = [
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
]

FEATURE_COLUMNS = [column for column in NUTRIENT_COLUMNS if column != "energy_kcal"]

DIARY_REQUIRED_COLUMNS = ("ID", "date", *MEAL_COLUMNS, "start_weight", "weight")

MIN_PRODUCTS_WITH_NUTRIENTS = 1

USDA_ENV_VAR = "DIPLOMA_USDA_DIR"
USDA_DIR_NAME = "FoodData_Central_csv_2026-04-30"


def resolve_usda_dir() -> Path:
    """Вернуть каталог USDA FoodData Central.

    Порядок поиска: переменная окружения ``DIPLOMA_USDA_DIR``, каталог
    ``data/FoodData_Central_csv_2026-04-30``, затем любой каталог ``data``,
    начинающийся с ``FoodData_Central``. Если каталог не найден, выбрасывается
    ``FileNotFoundError`` с инструкцией.
    """
    env_value = os.environ.get(USDA_ENV_VAR)
    if env_value:
        path = Path(env_value)
        if not path.is_dir():
            raise FileNotFoundError(
                f"Каталог USDA из {USDA_ENV_VAR} не найден: {path}"
            )
        return path

    candidates = [DATA_DIR / USDA_DIR_NAME]
    if DATA_DIR.is_dir():
        candidates.extend(sorted(DATA_DIR.glob("FoodData_Central*")))

    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        "Каталог USDA FoodData Central не найден. Скопируйте его в "
        f"{DATA_DIR / USDA_DIR_NAME} или задайте переменную окружения "
        f"{USDA_ENV_VAR}."
    )
