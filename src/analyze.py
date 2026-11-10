"""CLI профилирования датасетов.

Пример:
    uv run python -m src.analyze --sample 200000
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import DATA_PROFILE_PATH, DATASETS
from src.data_analyzer import DataAnalyzer
from src.data_loader import DataLoader

DEFAULT_DATASETS = ["diet_diary", "health_fitness", "daily_nutrition", "food_data"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Профилирование датасетов проекта")
    parser.add_argument(
        "--datasets",
        nargs="*",
        choices=sorted(DATASETS),
        default=DEFAULT_DATASETS,
        help="Датасеты для анализа (по умолчанию без тяжёлого MFP Parquet)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=200_000,
        help="Максимум строк на датасет (0 — все строки)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_PROFILE_PATH,
        help="Путь к markdown-отчёту",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    analyzer = DataAnalyzer()
    profiles = {}
    nrows = None if args.sample == 0 else args.sample

    for name in args.datasets:
        path = DATASETS[name]
        if not path.exists():
            print(f"Пропуск {name}: файл не найден — {path}")
            continue
        print(f"Анализ {name}: {path}")
        dataframe = DataLoader.load_path(path, nrows=nrows)
        profiles[name] = analyzer.profile(dataframe, name)
        print(
            f"  строк={profiles[name].n_rows}, "
            f"колонок={profiles[name].n_columns}, "
            f"дубликатов={profiles[name].duplicate_rows}"
        )

    if not profiles:
        print("Нет данных для анализа.")
        return 1

    output = analyzer.save_markdown(profiles, args.output)
    print(f"Отчёт сохранён: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
