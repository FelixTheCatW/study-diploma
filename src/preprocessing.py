"""Pipeline препроцессинга для кластеризации приёмов пищи."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, RobustScaler


def _clip_robust(values: np.ndarray) -> np.ndarray:
    """Ограничить выбросы в robust-z-пространстве.

    Без этого единичные продукты с экстремальной плотностью натрия или воды
    образуют кластеры из нескольких наблюдений и ломают выбор K.
    """
    return np.clip(values, -5.0, 5.0)


def make_preprocessing_pipeline(
    continuous_columns: Sequence[str],
    indicator_columns: Sequence[str],
) -> ColumnTransformer:
    """Медианная импутация и RobustScaler для непрерывных признаков.

    Missing-индикаторы передаются без масштабирования: это бинарные флаги.
    """
    continuous = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
            (
                "clip",
                FunctionTransformer(
                    _clip_robust,
                    feature_names_out="one-to-one",
                ),
            ),
        ]
    )
    transformers: list[tuple[str, object, list[str]]] = [
        ("continuous", continuous, list(continuous_columns))
    ]
    if indicator_columns:
        transformers.append(("missing", "passthrough", list(indicator_columns)))
    return ColumnTransformer(transformers=transformers, remainder="drop")
