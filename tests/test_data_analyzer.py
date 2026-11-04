from __future__ import annotations

import pandas as pd

from src.data_analyzer import DataAnalyzer


def test_profile_counts_missing_duplicates_and_constants():
    frame = pd.DataFrame(
        {
            "a": [1, 2, 2, None],
            "b": ["x", "x", "x", "y"],
            "c": [1, 1, 1, 1],
        }
    )
    profile = DataAnalyzer().profile(frame, "demo")

    assert profile.n_rows == 4
    assert profile.n_columns == 3
    assert profile.duplicate_rows == 1
    assert "c" in profile.constant_columns

    column_a = next(column for column in profile.columns if column["name"] == "a")
    assert column_a["n_missing"] == 1
    assert column_a["missing_share"] == 0.25
    assert profile.numeric_summary.loc["a", "count"] == 3


def test_profile_markdown_contains_sections():
    frame = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    profile = DataAnalyzer().profile(frame, "demo")
    markdown = profile.to_markdown()

    assert "## demo" in markdown
    assert "### Колонки" in markdown
    assert "### Числовые признаки" in markdown
    assert "`b`" in markdown


def test_diary_summary_counts(product_table):
    summary = DataAnalyzer().diary_summary(product_table)

    assert summary["n_products"] == 7
    assert summary["n_users"] == 2
    assert summary["n_days"] == 3
    assert summary["n_meals"] == 5
    assert summary["n_unique_products"] == 5
    assert summary["meal_counts"] == {"lunch": 3, "breakfast": 2}
    assert summary["match_coverage"] == 6 / 7
    assert "energy_outliers" in summary


def test_profile_file(tmp_path):
    path = tmp_path / "data.csv"
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_csv(path, index=False)

    profile = DataAnalyzer().profile_file(path, "from_file")

    assert profile.name == "from_file"
    assert profile.n_rows == 2


def test_save_markdown(tmp_path):
    analyzer = DataAnalyzer()
    profile = analyzer.profile(pd.DataFrame({"a": [1, 2]}), "demo")
    path = analyzer.save_markdown({"demo": profile}, tmp_path / "profile.md")

    assert path.exists()
    assert "## demo" in path.read_text(encoding="utf-8")
