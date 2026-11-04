from __future__ import annotations

import pandas as pd
import pytest

from src.data_loader import DataLoader


@pytest.fixture()
def frame() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


def test_csv_roundtrip(tmp_path, frame):
    path = tmp_path / "data.csv"
    DataLoader.save_dataframe(frame, path)

    loaded = DataLoader(path).load()
    pd.testing.assert_frame_equal(loaded, frame)


def test_parquet_roundtrip(tmp_path, frame):
    pytest.importorskip("pyarrow")
    path = tmp_path / "data.parquet"
    DataLoader.save_dataframe(frame, path)

    loaded = DataLoader.load_path(path)
    pd.testing.assert_frame_equal(loaded, frame)


def test_load_with_nrows_and_columns(tmp_path, frame):
    path = tmp_path / "data.csv"
    DataLoader.save_dataframe(frame, path)

    loaded = DataLoader.load_path(path, nrows=2, columns=["a"])
    assert list(loaded.columns) == ["a"]
    assert len(loaded) == 2


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="не найден"):
        DataLoader.load_path(tmp_path / "missing.csv")


def test_unsupported_suffix_raises(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Неподдерживаемый формат"):
        DataLoader.load_path(path)
