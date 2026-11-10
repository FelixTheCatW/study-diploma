"""CLI кластеризации приёмов пищи.

Пример:
    uv run python -m src.cluster --bootstrap 30
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import sklearn  # noqa: E402

from src.clustering import (  # noqa: E402
    PREDICTIVE_ALGORITHMS,
    bootstrap_stability,
    cluster_profiles,
    evaluate_k_sweep,
    fit_final_pipeline,
    pca_projection,
    select_k,
)
from src.config import BASE_DIR, MEAL_TABLE_PATH, REPORTS_DIR  # noqa: E402
from src.features import FeatureTable, build_feature_table, feature_matrix  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Кластеризация приёмов пищи")
    parser.add_argument("--meal-table", type=Path, default=MEAL_TABLE_PATH)
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR / "clustering",
    )
    parser.add_argument("--models-dir", type=Path, default=BASE_DIR / "models")
    parser.add_argument("--k-min", type=int, default=2)
    parser.add_argument("--k-max", type=int, default=8)
    parser.add_argument(
        "--algorithms",
        type=str,
        default="kmeans,gmm,agglomerative",
        help="Список через запятую: kmeans,gmm,agglomerative",
    )
    parser.add_argument("--bootstrap", type=int, default=30)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--sample-size", type=int, default=5000)
    parser.add_argument("--min-ari", type=float, default=0.75)
    parser.add_argument("--min-share", type=float, default=0.05)
    parser.add_argument(
        "--no-save-model",
        action="store_true",
        help="Не сохранять финальный Pipeline",
    )
    return parser


def _md_table(table: pd.DataFrame, float_format: str = ".4f") -> str:
    columns = list(table.columns)
    lines = [
        "| " + " | ".join(str(column) for column in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for _, row in table.iterrows():
        values: list[str] = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                if np.isfinite(value) and float(value).is_integer():
                    values.append(str(int(value)))
                else:
                    values.append(f"{value:{float_format}}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _stability_summary(stability: pd.DataFrame) -> pd.DataFrame:
    if stability.empty:
        return pd.DataFrame(
            columns=[
                "algorithm",
                "k",
                "median_ari",
                "q1_ari",
                "q3_ari",
                "median_min_cluster_share",
                "n_bootstrap",
            ]
        )
    return (
        stability.groupby(["algorithm", "k"], as_index=False)
        .agg(
            median_ari=("ari", "median"),
            q1_ari=("ari", lambda values: values.quantile(0.25)),
            q3_ari=("ari", lambda values: values.quantile(0.75)),
            median_min_cluster_share=("min_cluster_share", "median"),
            n_bootstrap=("ari", "size"),
        )
        .reset_index(drop=True)
    )


def _plot_k_selection(sweep: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for algorithm, group in sweep.groupby("algorithm"):
        axis.plot(group["k"], group["silhouette"], marker="o", label=algorithm)
    axis.set_xlabel("K")
    axis.set_ylabel("Silhouette")
    axis.set_title("Выбор K по silhouette")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_stability(summary: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    if not summary.empty:
        for algorithm, group in summary.groupby("algorithm"):
            axis.plot(group["k"], group["median_ari"], marker="o", label=algorithm)
            axis.fill_between(
                group["k"],
                group["q1_ari"],
                group["q3_ari"],
                alpha=0.2,
            )
    axis.axhline(0.75, color="black", linestyle="--", linewidth=1)
    axis.set_xlabel("K")
    axis.set_ylabel("Bootstrap ARI")
    axis.set_title("Устойчивость кластеризации")
    axis.set_ylim(0, 1)
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_profiles(profiles: pd.DataFrame, path: Path) -> None:
    continuous = [
        feature
        for feature in profiles["feature"].unique()
        if not feature.startswith("missing_")
    ]
    table = profiles[profiles["feature"].isin(continuous)].pivot(
        index="cluster", columns="feature", values="z_score"
    )
    figure, axis = plt.subplots(figsize=(max(8, len(continuous) * 0.8), 4.5))
    image = axis.imshow(table.to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-2, vmax=2)
    axis.set_xticks(range(len(table.columns)), table.columns, rotation=45, ha="right")
    axis.set_yticks(
        range(len(table.index)), [f"cluster {value}" for value in table.index]
    )
    axis.set_title("Профили кластеров: z-score относительно среднего")
    figure.colorbar(image, ax=axis, shrink=0.8)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_pca(projection: pd.DataFrame, path: Path) -> None:
    sample = projection.sample(min(3000, len(projection)), random_state=42)
    figure, axis = plt.subplots(figsize=(6.5, 5))
    scatter = axis.scatter(
        sample["pc1"],
        sample["pc2"],
        c=sample["cluster"],
        cmap="tab10",
        s=10,
        alpha=0.7,
    )
    axis.set_xlabel("PC1")
    axis.set_ylabel("PC2")
    axis.set_title("PCA-проекция кластеров")
    figure.colorbar(scatter, ax=axis, label="cluster")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _data_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report(
    path: Path,
    *,
    features: FeatureTable,
    sweep: pd.DataFrame,
    stability_summary: pd.DataFrame,
    selected: dict[str, object],
    sizes: pd.DataFrame,
    profiles: pd.DataFrame,
    metadata: dict[str, object],
) -> None:
    continuous = [
        feature
        for feature in profiles["feature"].unique()
        if not feature.startswith("missing_")
    ]
    top = profiles[profiles["feature"].isin(continuous)].copy()
    top["abs_z"] = top["z_score"].abs()
    top = (
        top.sort_values(["cluster", "abs_z"], ascending=[True, False])
        .groupby("cluster", sort=True)
        .head(3)
    )
    top["direction"] = np.where(top["z_score"] >= 0, "выше", "ниже")

    selection = pd.DataFrame(
        [
            {
                "algorithm": selected["algorithm"],
                "k": selected["k"],
                "stable": selected["stable"],
                "median_ari": selected["median_ari"],
                "silhouette": selected["silhouette"],
                "min_cluster_share": selected["min_cluster_share"],
                "reason": selected["reason"],
            }
        ]
    )

    lines = [
        "# Кластеризация приёмов пищи",
        "",
        f"Дата запуска: {metadata['created_at']}",
        "",
        "## Данные",
        "",
        f"- Всего приёмов в таблице: {metadata['n_meal_table']}",
        f"- После фильтра core_complete: {features.n_input}",
        f"- Отброшено без валидного ядра: {features.n_dropped}",
        f"- В кластеризации: {len(features.frame)}",
        f"- Признаков: {len(features.feature_columns)} "
        f"({len(features.continuous_columns)} непрерывных, "
        f"{len(features.indicator_columns)} индикаторов)",
        f"- SHA-256 таблицы приёмов: `{metadata['data_sha256']}`",
        "",
        "## Выбор K",
        "",
        "K выбирается по устойчивости и размеру кластеров, а не по максимуму "
        "silhouette: берётся максимальное K, прошедшее пороги, затем лучший "
        "алгоритм при этом K. Порог median ARI: "
        f"{metadata['min_ari']}; минимальная доля кластера: {metadata['min_share']}.",
        "",
        _md_table(selection),
        "",
        "### Внутренние метрики",
        "",
        _md_table(
            sweep[
                [
                    "algorithm",
                    "k",
                    "n_samples",
                    "silhouette",
                    "davies_bouldin",
                    "calinski_harabasz",
                    "min_cluster_share",
                ]
            ]
        ),
        "",
        "### Устойчивость",
        "",
        _md_table(stability_summary)
        if not stability_summary.empty
        else "Устойчивость не считалась.",
        "",
        "## Размеры кластеров",
        "",
        _md_table(sizes),
        "",
        "## Топ различий по кластерам",
        "",
        _md_table(
            top[
                [
                    "cluster",
                    "feature",
                    "cluster_mean",
                    "overall_mean",
                    "z_score",
                    "direction",
                ]
            ]
        ),
        "",
        "Кластер с |z| < 0.3 по всем признакам интерпретируется как "
        "смешанный/типичный, а не как отдельный выраженный паттерн.",
        "",
        "## Ограничения",
        "",
        "- Внешних меток нет: accuracy не используется, метрики внутренние.",
        "- Основная выборка — приёмы с полным покрытием energy + БЖУ; "
        "неполные приёмы исключены, а не заполнены нулём.",
        "- Доли БЖУ считаются по массе и преобразуются в ILR; выбросы "
        "ограничиваются ±5 в robust-z-пространстве.",
        "- Agglomerative считается на подвыборке и не используется для predict().",
        "- 32 продукта с неоднозначными названиями не сопоставлены с USDA; "
        "приёмы с ними не входят в основную выборку.",
        "- Профили кластеров — описательные; названия паттернов требуют "
        "экспертной валидации.",
        "",
        "## Воспроизведение",
        "",
        "```powershell",
        "uv run python -m src.cluster --bootstrap 30",
        "uv run pytest -q",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    algorithms = [
        value.strip() for value in args.algorithms.split(",") if value.strip()
    ]
    k_values = list(range(args.k_min, args.k_max + 1))

    meal_table = pd.read_csv(args.meal_table)
    features = build_feature_table(meal_table)
    x = feature_matrix(features)
    print(
        f"Приёмов: вход={features.n_input}, отброшено={features.n_dropped}, "
        f"в кластеризации={len(x)}, признаков={len(features.feature_columns)}"
    )

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    sweep = evaluate_k_sweep(
        x,
        features.continuous_columns,
        features.indicator_columns,
        algorithms=algorithms,
        k_values=k_values,
        random_state=args.random_state,
        sample_size=args.sample_size,
    )
    sweep.to_csv(reports_dir / "k_selection.csv", index=False, encoding="utf-8")

    stability_frames: list[pd.DataFrame] = []
    if args.bootstrap > 0:
        for algorithm in algorithms:
            if algorithm not in PREDICTIVE_ALGORITHMS:
                continue
            for k in k_values:
                stability = bootstrap_stability(
                    x,
                    features.continuous_columns,
                    features.indicator_columns,
                    algorithm=algorithm,
                    k=k,
                    n_bootstrap=args.bootstrap,
                    random_state=args.random_state,
                )
                stability["algorithm"] = algorithm
                stability["k"] = k
                stability_frames.append(stability)
    stability = (
        pd.concat(stability_frames, ignore_index=True)
        if stability_frames
        else pd.DataFrame()
    )
    stability.to_csv(reports_dir / "stability.csv", index=False, encoding="utf-8")
    stability_summary = _stability_summary(stability)
    stability_summary.to_csv(
        reports_dir / "stability_summary.csv", index=False, encoding="utf-8"
    )

    selected = select_k(
        sweep,
        stability,
        min_ari=args.min_ari,
        min_share=args.min_share,
    )
    print(
        f"Выбрано: {selected['algorithm']} K={selected['k']} "
        f"stable={selected['stable']} ARI={selected['median_ari']:.3f}"
    )

    pipeline, labels = fit_final_pipeline(
        x,
        features.continuous_columns,
        features.indicator_columns,
        algorithm=str(selected["algorithm"]),
        k=int(selected["k"]),
        random_state=args.random_state,
    )
    profiles, sizes = cluster_profiles(
        features.frame,
        labels,
        features.continuous_columns,
        features.indicator_columns,
    )
    profiles.to_csv(reports_dir / "cluster_profiles.csv", index=False, encoding="utf-8")
    sizes.to_csv(reports_dir / "cluster_sizes.csv", index=False, encoding="utf-8")

    for name, plotter in (
        ("k_selection.png", lambda path: _plot_k_selection(sweep, path)),
        ("stability.png", lambda path: _plot_stability(stability_summary, path)),
        ("cluster_profiles.png", lambda path: _plot_profiles(profiles, path)),
        (
            "pca_clusters.png",
            lambda path: _plot_pca(
                pca_projection(
                    features.frame,
                    features.continuous_columns,
                    features.indicator_columns,
                    labels,
                    random_state=args.random_state,
                ),
                path,
            ),
        ),
    ):
        plotter(reports_dir / name)

    if not args.no_save_model:
        models_dir = Path(args.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, models_dir / "clustering_pipeline.joblib")

    metadata = {
        "created_at": pd.Timestamp.now().isoformat(),
        "data_sha256": _data_hash(Path(args.meal_table)),
        "n_meal_table": int(len(meal_table)),
        "n_input": features.n_input,
        "n_dropped": features.n_dropped,
        "n_samples": int(len(x)),
        "feature_columns": list(features.feature_columns),
        "continuous_columns": list(features.continuous_columns),
        "indicator_columns": list(features.indicator_columns),
        "algorithms": algorithms,
        "k_values": k_values,
        "selected": selected,
        "min_ari": args.min_ari,
        "min_share": args.min_share,
        "bootstrap": args.bootstrap,
        "random_state": args.random_state,
        "versions": {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "cluster_sizes": sizes.to_dict(orient="records"),
    }
    (reports_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    _write_report(
        reports_dir / "clustering_report.md",
        features=features,
        sweep=sweep,
        stability_summary=stability_summary,
        selected=selected,
        sizes=sizes,
        profiles=profiles,
        metadata=metadata,
    )
    print(f"Отчёты: {reports_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
