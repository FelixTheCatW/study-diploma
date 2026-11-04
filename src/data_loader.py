"""Загрузка и сохранение табличных данных.

Поддерживаются CSV и Parquet. Parquet читается через pyarrow; при его
отсутствии выбрасывается понятное сообщение об установке зависимости.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

SUPPORTED_SUFFIXES = {".csv", ".parquet"}


class DataLoader:
    """Загрузчик табличных файлов с проверкой пути и формата."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, **kwargs: Any) -> pd.DataFrame:
        """Загрузить файл, переданный в конструкторе."""
        return self.load_path(self.path, **kwargs)

    @staticmethod
    def load_path(
        path: str | Path,
        *,
        nrows: int | None = None,
        columns: list[str] | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Загрузить CSV или Parquet.

        Параметр ``columns`` ограничивает набор колонок, ``nrows`` — число
        строк (для Parquet ограничение применяется после чтения).
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")

        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, nrows=nrows, usecols=columns, **kwargs)

        if suffix == ".parquet":
            try:
                import pyarrow  # noqa: F401
            except ImportError as exc:
                raise ImportError(
                    "Для чтения Parquet установите pyarrow: "
                    "uv sync --extra dev или pip install pyarrow"
                ) from exc
            data = pd.read_parquet(path, columns=columns, **kwargs)
            if nrows is not None:
                data = data.head(nrows)
            return data

        raise ValueError(
            f"Неподдерживаемый формат {suffix!r}. "
            f"Допустимые форматы: {sorted(SUPPORTED_SUFFIXES)}"
        )

    @staticmethod
    def save_dataframe(
        dataframe: pd.DataFrame,
        path: str | Path,
        *,
        index: bool = False,
    ) -> None:
        """Сохранить DataFrame в CSV или Parquet."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()

        if suffix == ".csv":
            dataframe.to_csv(path, index=index)
            return
        if suffix == ".parquet":
            try:
                import pyarrow  # noqa: F401
            except ImportError as exc:
                raise ImportError(
                    "Для записи Parquet установите pyarrow: "
                    "uv sync --extra dev или pip install pyarrow"
                ) from exc
            dataframe.to_parquet(path, index=index)
            return

        raise ValueError(
            f"Неподдерживаемый формат {suffix!r}. "
            f"Допустимые форматы: {sorted(SUPPORTED_SUFFIXES)}"
        )


def load_csv(
    path: str | Path,
    *,
    nrows: int | None = None,
    columns: list[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Краткая обёртка для загрузки CSV."""
    return DataLoader.load_path(path, nrows=nrows, columns=columns, **kwargs)


def load_parquet(
    path: str | Path,
    *,
    nrows: int | None = None,
    columns: list[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Краткая обёртка для загрузки Parquet."""
    return DataLoader.load_path(path, nrows=nrows, columns=columns, **kwargs)
