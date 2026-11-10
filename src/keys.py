"""Стабильные идентификаторы приёмов пищи."""

from __future__ import annotations

import pandas as pd


def meal_id_series(frame: pd.DataFrame) -> pd.Series:
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return (
        frame["id"].astype("string").fillna("")
        + "|"
        + dates.astype("string").fillna("")
        + "|"
        + frame["meal"].astype("string").fillna("")
    )
