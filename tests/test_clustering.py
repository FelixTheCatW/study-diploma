from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_blobs

from src.clustering import (
    bootstrap_stability,
    cluster_profiles,
    evaluate_k_sweep,
    fit_final_pipeline,
    pca_projection,
    select_k,
)

CONTINUOUS = ("f1", "f2", "f3")
INDICATORS = ("missing_f1",)


def _blobs() -> pd.DataFrame:
    values, _ = make_blobs(
        n_samples=150,
        centers=3,
        n_features=3,
        cluster_std=0.35,
        random_state=42,
    )
    frame = pd.DataFrame(values, columns=list(CONTINUOUS))
    frame["missing_f1"] = np.arange(len(frame)) % 2
    return frame


def test_k_sweep_and_stability_are_reproducible():
    frame = _blobs()
    sweep = evaluate_k_sweep(
        frame,
        CONTINUOUS,
        INDICATORS,
        algorithms=("kmeans", "gmm"),
        k_values=(2, 3, 4),
        random_state=42,
        sample_size=100,
    )
    assert len(sweep) == 6
    assert np.isfinite(sweep["silhouette"]).all()
    assert (sweep["min_cluster_share"] > 0).all()

    stability = bootstrap_stability(
        frame,
        CONTINUOUS,
        INDICATORS,
        algorithm="kmeans",
        k=3,
        n_bootstrap=5,
        random_state=42,
    )
    assert len(stability) == 5
    assert stability["ari"].between(0, 1).all()
    assert stability["ari"].median() > 0.8


def test_select_k_prefers_stable_candidate():
    frame = _blobs()
    sweep = evaluate_k_sweep(
        frame,
        CONTINUOUS,
        INDICATORS,
        algorithms=("kmeans",),
        k_values=(2, 3, 4),
        random_state=42,
        sample_size=100,
    )
    stability = bootstrap_stability(
        frame,
        CONTINUOUS,
        INDICATORS,
        algorithm="kmeans",
        k=3,
        n_bootstrap=5,
        random_state=42,
    )
    stability["algorithm"] = "kmeans"
    stability["k"] = 3

    selected = select_k(sweep, stability, min_ari=0.5, min_share=0.05)
    assert selected["algorithm"] == "kmeans"
    assert selected["k"] == 3
    assert selected["stable"] is True


def test_final_pipeline_profiles_and_save(tmp_path):
    frame = _blobs()
    pipeline, labels = fit_final_pipeline(
        frame,
        CONTINUOUS,
        INDICATORS,
        algorithm="kmeans",
        k=3,
        random_state=42,
    )
    assert len(labels) == len(frame)
    assert pipeline.predict(frame).shape == (len(frame),)

    path = tmp_path / "pipeline.joblib"
    joblib.dump(pipeline, path)
    loaded = joblib.load(path)
    assert (loaded.predict(frame) == labels).all()

    profiles, sizes = cluster_profiles(frame, labels, CONTINUOUS, INDICATORS)
    assert set(sizes["cluster"]) == {0, 1, 2}
    assert sizes["n"].sum() == len(frame)
    assert set(profiles["cluster"]) == {0, 1, 2}

    projection = pca_projection(frame, CONTINUOUS, INDICATORS, labels)
    assert projection.shape == (len(frame), 3)


def test_agglomerative_uses_subsample():
    frame = _blobs()
    sweep = evaluate_k_sweep(
        frame,
        CONTINUOUS,
        INDICATORS,
        algorithms=("agglomerative",),
        k_values=(3,),
        random_state=42,
        sample_size=50,
    )
    assert len(sweep) == 1
    assert sweep.iloc[0]["n_samples"] == 50


def test_bootstrap_rejects_agglomerative():
    with pytest.raises(ValueError, match="K-Means"):
        bootstrap_stability(
            _blobs(),
            CONTINUOUS,
            INDICATORS,
            algorithm="agglomerative",
            k=3,
            n_bootstrap=2,
        )
