from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.datasets import make_blobs

from src.sensitivity import _fit_labels, _fit_on_all_predict_core, _min_cluster_share


def _blobs() -> pd.DataFrame:
    values, _ = make_blobs(
        n_samples=60,
        centers=3,
        n_features=3,
        cluster_std=0.3,
        random_state=42,
    )
    frame = pd.DataFrame(values, columns=["f1", "f2", "f3"])
    frame["missing_f1"] = 0
    return frame


def test_fit_variant_and_min_share():
    frame = _blobs()
    labels = _fit_labels(
        frame,
        ["f1", "f2", "f3"],
        ["missing_f1"],
        algorithm="kmeans",
        k=3,
        clip=True,
        random_state=42,
    )
    assert len(labels) == len(frame)
    assert 0 < _min_cluster_share(labels) <= 1


def test_fit_on_all_predict_core():
    frame = _blobs()
    labels = _fit_on_all_predict_core(
        frame,
        frame,
        ["f1", "f2", "f3"],
        ["missing_f1"],
        k=3,
        random_state=42,
    )
    assert len(labels) == len(frame)
    assert len(np.unique(labels)) == 3
