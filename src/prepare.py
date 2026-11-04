"""CLI подготовки данных DietDiary + USDA.

Пример:
    $env:DIPLOMA_USDA_DIR = "D:\\study\\ml\\study-ml\\data\\FoodData_Central_csv_2026-04-30"
    uv run python -m src.prepare --force
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.config import DIARY_CSV, PROCESSED_DIR
from src.data_preparer import DataPreparer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Подготовка данных DietDiary + USDA")
    parser.add_argument("--diary", type=Path, default=DIARY_CSV)
    parser.add_argument(
        "--usda-dir",
        type=Path,
        default=None,
        help="Каталог USDA FoodData Central (иначе DIPLOMA_USDA_DIR или data/)",
    )
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--force", action="store_true", help="Пересобрать кэш")
    parser.add_argument(
        "--min-products",
        type=int,
        default=1,
        help="Минимум продуктов с нутриентами для флага is_reliable",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    preparer = DataPreparer(
        diary_path=args.diary,
        usda_dir=args.usda_dir,
        processed_dir=args.processed_dir,
        min_products_with_nutrients=args.min_products,
    )

    try:
        product, meal, day = preparer.prepare(force=args.force)
    except FileNotFoundError as exc:
        print(f"Ошибка подготовки данных: {exc}")
        return 1
    except ImportError as exc:
        print(f"Ошибка зависимости: {exc}")
        return 1

    summary = preparer.summary(product, meal, day)
    print("Подготовка завершена.")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(f"  product_table: {preparer.product_table_path}")
    print(f"  meal_table: {preparer.meal_table_path}")
    print(f"  day_table: {preparer.day_table_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
