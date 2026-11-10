"""Кластеризация приёмов пищи: K-Means, GMM, Agglomerative.

Метрики внутренние: внешних меток нет. Выбор K опирается не только на
silhouette, но и на bootstrap-устойчивость и минимальную долю кластера.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline

from src.preprocessing import make_preprocessing_pipeline

ALGORITHMS = ("kmeans", "gmm", "agglomerative")
PREDICTIVE_ALGORITHMS = ("kmeans", "gmm")


@dataclass(frozen=True)
class FitResult:
    algorithm: str
    k: int
    labels: np.ndarray
    model: object
    preprocessing: object
    metrics: dict[str, float]
    sample_indices: np.ndarray | None = None


def make_model(algorithm: str, k: int, random_state: int = 42) -> object:
    if algorithm == "kmeans":
        return KMeans(n_clusters=k, n_init=50, max_iter=500, random_state=random_state)
    if algorithm == "gmm":
        return GaussianMixture(
            n_components=k,
            covariance_type="full",
            n_init=10,
            max_iter=500,
            reg_covar=1e-6,
            random_state=random_state,
        )
    if algorithm == "agglomerative":
        return AgglomerativeClustering(n_clusters=k, linkage="ward")
    raise ValueError(f"Неизвестный алгоритм: {algorithm}")


def _cluster_share(labels: np.ndarray) -> float:
    counts = np.bincount(labels[labels >= 0])
    if counts.size == 0:
        return 0.0
    return float(counts.min() / counts.sum())


def _metrics(
    x: np.ndarray,
    labels: np.ndarray,
    model: object,
    random_state: int,
) -> dict[str, float]:
    n_clusters = len(set(labels.tolist()) - {-1})
    metrics: dict[str, float] = {
        "n_clusters": float(n_clusters),
        "min_cluster_share": _cluster_share(labels),
    }
    if n_clusters < 2:
        metrics.update(
            {
                "silhouette": float("nan"),
                "davies_bouldin": float("nan"),
                "calinski_harabasz": float("nan"),
            }
        )
    else:
        sample_size = min(5000, len(x))
        metrics["silhouette"] = float(
            silhouette_score(
                x,
                labels,
                sample_size=sample_size,
                random_state=random_state,
            )
        )
        metrics["davies_bouldin"] = float(davies_bouldin_score(x, labels))
        metrics["calinski_harabasz"] = float(calinski_harabasz_score(x, labels))

    if hasattr(model, "inertia_"):
        metrics["inertia"] = float(model.inertia_)
    if isinstance(model, GaussianMixture):
        metrics["bic"] = float(model.bic(x))
        metrics["aic"] = float(model.aic(x))
    return metrics


def fit_algorithm(
    x: pd.DataFrame,
    continuous_columns: Sequence[str],
    indicator_columns: Sequence[str],
    algorithm: str,
    k: int,
    *,
    random_state: int = 42,
    sample_size: int = 5000,
) -> FitResult:
    """Обучить один алгоритм. Agglomerative считается на подвыборке."""
    sample_indices: np.ndarray | None = None
    if algorithm == "agglomerative" and len(x) > sample_size:
        rng = np.random.default_rng(random_state)
        sample_indices = np.sort(rng.choice(len(x), size=sample_size, replace=False))
        fit_x = x.iloc[sample_indices]
    else:
        fit_x = x

    preprocessing = make_preprocessing_pipeline(continuous_columns, indicator_columns)
    transformed = preprocessing.fit_transform(fit_x)
    model = make_model(algorithm, k, random_state=random_state)
    labels = model.fit_predict(transformed) if hasattr(model, "fit_predict") else None
    if labels is None:
        model.fit(transformed)
        labels = model.predict(transformed)
    labels = np.asarray(labels, dtype=int)
    metrics = _metrics(np.asarray(transformed), labels, model, random_state)
    return FitResult(
        algorithm=algorithm,
        k=k,
        labels=labels,
        model=model,
        preprocessing=preprocessing,
        metrics=metrics,
        sample_indices=sample_indices,
    )


def evaluate_k_sweep(
    x: pd.DataFrame,
    continuous_columns: Sequence[str],
    indicator_columns: Sequence[str],
    *,
    algorithms: Sequence[str] = ALGORITHMS,
    k_values: Sequence[int] = range(2, 9),
    random_state: int = 42,
    sample_size: int = 5000,
) -> pd.DataFrame:
    rows: list[dict[str, float | str | int]] = []
    for algorithm in algorithms:
        for k in k_values:
            result = fit_algorithm(
                x,
                continuous_columns,
                indicator_columns,
                algorithm,
                k,
                random_state=random_state,
                sample_size=sample_size,
            )
            rows.append(
                {
                    "algorithm": algorithm,
                    "k": k,
                    "n_samples": len(result.labels),
                    **result.metrics,
                }
            )
    return pd.DataFrame(rows)


def bootstrap_stability(
    x: pd.DataFrame,
    continuous_columns: Sequence[str],
    indicator_columns: Sequence[str],
    *,
    algorithm: str,
    k: int,
    n_bootstrap: int = 30,
    subsample: float = 0.8,
    random_state: int = 42,
) -> pd.DataFrame:
    """ARI между полным решением и решением на подвыборке.

    Pipeline обучается заново на каждой подвыборке, затем применяется ко
    всем наблюдениям. Это проверяет устойчивость препроцессинга и модели.
    """
    if algorithm not in PREDICTIVE_ALGORITHMS:
        raise ValueError("Устойчивость считается только для K-Means и GMM")

    reference = make_preprocessing_pipeline(continuous_columns, indicator_columns)
    reference_matrix = reference.fit_transform(x)
    reference_model = make_model(algorithm, k, random_state=random_state)
    reference_model.fit(reference_matrix)
    reference_labels = np.asarray(reference_model.predict(reference_matrix), dtype=int)

    rng = np.random.default_rng(random_state)
    size = max(2, int(len(x) * subsample))
    rows: list[dict[str, float | int]] = []
    for iteration in range(n_bootstrap):
        indices = np.sort(rng.choice(len(x), size=size, replace=False))
        preprocessing = make_preprocessing_pipeline(
            continuous_columns, indicator_columns
        )
        transformed = preprocessing.fit_transform(x.iloc[indices])
        model = make_model(algorithm, k, random_state=random_state + iteration)
        model.fit(transformed)
        labels = np.asarray(model.predict(preprocessing.transform(x)), dtype=int)
        rows.append(
            {
                "iteration": iteration,
                "ari": float(adjusted_rand_score(reference_labels, labels)),
                "min_cluster_share": _cluster_share(labels),
                "n_samples": size,
            }
        )
    return pd.DataFrame(rows)


def summarize_stability(stability: pd.DataFrame) -> dict[str, float]:
    return {
        "median_ari": float(stability["ari"].median()),
        "q1_ari": float(stability["ari"].quantile(0.25)),
        "q3_ari": float(stability["ari"].quantile(0.75)),
        "median_min_cluster_share": float(stability["min_cluster_share"].median()),
        "n_bootstrap": float(len(stability)),
    }


def select_k(
    sweep: pd.DataFrame,
    stability: pd.DataFrame,
    *,
    min_ari: float = 0.75,
    min_share: float = 0.05,
) -> dict[str, object]:
    """Выбрать K по устойчивости, размеру кластеров и silhouette."""
    if stability.empty:
        raise ValueError("Нет таблицы устойчивости для выбора K")

    summary = (
        stability.groupby(["algorithm", "k"], as_index=False)
        .apply(
            lambda group: pd.Series(
                {
                    "median_ari": group["ari"].median(),
                    "q1_ari": group["ari"].quantile(0.25),
                    "q3_ari": group["ari"].quantile(0.75),
                    "median_min_cluster_share": group["min_cluster_share"].median(),
                }
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    candidates = sweep.merge(summary, on=["algorithm", "k"], how="inner")
    candidates = candidates[candidates["min_cluster_share"] >= min_share]
    if candidates.empty:
        raise ValueError("Ни один K не прошёл порог минимальной доли кластера")

    stable = candidates[candidates["median_ari"] >= min_ari]
    if stable.empty:
        best = candidates.sort_values(
            ["median_ari", "silhouette", "min_cluster_share"],
            ascending=[False, False, False],
        ).iloc[0]
    else:
        max_k = int(stable["k"].max())
        best = (
            stable[stable["k"] == max_k]
            .sort_values(
                ["median_ari", "silhouette", "min_cluster_share"],
                ascending=[False, False, False],
            )
            .iloc[0]
        )
    return {
        "algorithm": str(best["algorithm"]),
        "k": int(best["k"]),
        "stable": bool(best["median_ari"] >= min_ari),
        "median_ari": float(best["median_ari"]),
        "silhouette": float(best["silhouette"]),
        "min_cluster_share": float(best["min_cluster_share"]),
        "reason": "stable" if bool(best["median_ari"] >= min_ari) else "best_effort",
    }


def fit_final_pipeline(
    x: pd.DataFrame,
    continuous_columns: Sequence[str],
    indicator_columns: Sequence[str],
    *,
    algorithm: str,
    k: int,
    random_state: int = 42,
) -> tuple[Pipeline, np.ndarray]:
    preprocessing = make_preprocessing_pipeline(continuous_columns, indicator_columns)
    model = make_model(algorithm, k, random_state=random_state)
    pipeline = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("clustering", model),
        ]
    )
    pipeline.fit(x)
    labels = np.asarray(pipeline.predict(x), dtype=int)
    return pipeline, labels


def cluster_profiles(
    frame: pd.DataFrame,
    labels: np.ndarray,
    continuous_columns: Sequence[str],
    indicator_columns: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = frame[list(continuous_columns) + list(indicator_columns)].copy()
    data["cluster"] = labels
    overall_mean = data[list(continuous_columns)].mean()
    overall_std = data[list(continuous_columns)].std().replace(0, 1.0)

    rows: list[dict[str, object]] = []
    for cluster, group in data.groupby("cluster", sort=True):
        for column in continuous_columns:
            mean = float(group[column].mean())
            z_score = float((mean - overall_mean[column]) / overall_std[column])
            rows.append(
                {
                    "cluster": int(cluster),
                    "feature": column,
                    "cluster_mean": mean,
                    "overall_mean": float(overall_mean[column]),
                    "z_score": z_score,
                }
            )
        for column in indicator_columns:
            rows.append(
                {
                    "cluster": int(cluster),
                    "feature": column,
                    "cluster_mean": float(group[column].mean()),
                    "overall_mean": float(data[column].mean()),
                    "z_score": float("nan"),
                }
            )
    profiles = pd.DataFrame(rows)
    sizes = (
        data.groupby("cluster", as_index=False)
        .size()
        .rename(columns={"size": "n"})
        .assign(share=lambda table: table["n"] / len(data))
    )
    return profiles, sizes


def pca_projection(
    frame: pd.DataFrame,
    continuous_columns: Sequence[str],
    indicator_columns: Sequence[str],
    labels: np.ndarray,
    *,
    random_state: int = 42,
) -> pd.DataFrame:
    preprocessing = make_preprocessing_pipeline(continuous_columns, indicator_columns)
    transformed = preprocessing.fit_transform(
        frame[list(continuous_columns) + list(indicator_columns)]
    )
    pca = PCA(n_components=2, random_state=random_state)
    components = pca.fit_transform(transformed)
    return pd.DataFrame(
        {
            "pc1": components[:, 0],
            "pc2": components[:, 1],
            "cluster": labels,
        }
    )
