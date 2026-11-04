from __future__ import annotations

import pytest

from src.config import USDA_ENV_VAR, resolve_usda_dir


def test_usda_dir_from_environment(monkeypatch, usda_dir):
    monkeypatch.setenv(USDA_ENV_VAR, str(usda_dir))

    assert resolve_usda_dir() == usda_dir


def test_invalid_usda_dir_from_environment_raises(monkeypatch, tmp_path):
    monkeypatch.setenv(USDA_ENV_VAR, str(tmp_path / "missing"))

    with pytest.raises(FileNotFoundError, match=USDA_ENV_VAR):
        resolve_usda_dir()
