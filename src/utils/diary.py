"""Разбор дневника питания DietDiary.

В исходном CSV одна строка — день пользователя; три колонки (breakfast,
lunch, supper) содержат изображения и перечень продуктов, разделённые
маркером ``|||``. Функция :func:`parse_diary` превращает такие строки в
таблицу уровня «продукт в приёме пищи».
"""

from __future__ import annotations

from os import PathLike

import pandas as pd

DataInput = pd.DataFrame | str | PathLike[str]

MEAL_COLUMNS = ("breakfast", "lunch", "supper")
NON_MEAL_COLUMNS = ("ID", "date", "start_weight", "weight")
IMAGES_MARKER = "|||"

OUT_COLUMNS = [
    "id",
    "date",
    "meal",
    "product",
    "start_weight",
    "weight",
    "images",
    "n_images",
]


def _read(data: DataInput) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    return pd.read_csv(data)


def split_meal_cell(cell: object) -> tuple[list[str], list[str]]:
    """Разделить ячейку приёма на пути изображений и список продуктов.

    Возвращает два списка: изображения (через ``;``) и продукты (через
    пробелы). Пустые значения игнорируются.
    """
    text = "" if pd.isna(cell) else str(cell)
    images_part, _, products_part = text.partition(IMAGES_MARKER)
    images = [item.strip() for item in images_part.split(";") if item.strip()]
    products = products_part.split()
    return images, products


def parse_diary(diary: DataInput) -> pd.DataFrame:
    """Преобразовать дневник в таблицу уровня «продукт в приёме».

    Одна запись результата соответствует одному продукту в одном приёме.
    Дубликаты продуктов не удаляются. Изображения сохраняются строкой и
    счётчиком, чтобы их можно было использовать в фото-треке.
    """
    frame = _read(diary)
    missing = [
        column
        for column in NON_MEAL_COLUMNS + MEAL_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"В дневнике отсутствуют колонки: {missing}")

    records: list[dict[str, object]] = []
    for row in frame.to_dict(orient="records"):
        base = {column: row[column] for column in NON_MEAL_COLUMNS}
        base["id"] = base.pop("ID")
        base["date"] = pd.to_datetime(base["date"], errors="coerce")

        for meal in MEAL_COLUMNS:
            images, products = split_meal_cell(row[meal])
            if not products:
                continue
            image_text = ";".join(images) if images else None
            for product in products:
                records.append(
                    {
                        **base,
                        "meal": meal,
                        "product": product,
                        "images": image_text,
                        "n_images": len(images),
                    }
                )

    return pd.DataFrame.from_records(records, columns=OUT_COLUMNS)
