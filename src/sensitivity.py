"""Sensitivity-анализ кластеризации.

Проверяет, держится ли решение при смене K, алгоритма, набора признаков,
clip и выборки. Это не выбор модели по максимуму метрики, а проверка
устойчивости уже принятого решения.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from sklearn.pipeline import Pipeline

from src.clustering import make_model
from src.config import MEAL_TABLE_PATH, PRODUCT_TABLE_PATH, REPORTS_DIR
from src.features import build_feature_table, feature_matrix
from src.keys import meal_id_series
from src.preprocessing import make_preprocessing_pipeline


def _min_cluster_share(labels: np.ndarray) -> float:
    counts = np.bincount(labels[labels >= 0])
    if counts.size == 0:
        return 0.0
    return float(counts.min() / counts.sum())


def _fit_labels(
    x: pd.DataFrame,
    continuous: list[str],
    indicators: list[str],
    *,
    algorithm: str,
    k: int,
    clip: bool,
    random_state: int,
) -> np.ndarray:
    columns = [column for column in [*continuous, *indicators] if column in x.columns]
    preprocessing = make_preprocessing_pipeline(
        continuous,
        indicators,
        clip=clip,
    )
    model = make_model(algorithm, k, random_state=random_state)
    pipeline = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("clustering", model),
        ]
    )
    pipeline.fit(x[columns])
    return np.asarray(pipeline.predict(x[columns]), dtype=int)


def _fit_on_all_predict_core(
    x_all: pd.DataFrame,
    x_core: pd.DataFrame,
    continuous: list[str],
    indicators: list[str],
    *,
    k: int,
    random_state: int,
) -> np.ndarray:
    columns = [
        column for column in [*continuous, *indicators] if column in x_all.columns
    ]
    preprocessing = make_preprocessing_pipeline(continuous, indicators, clip=True)
    model = make_model("kmeans", k, random_state=random_state)
    pipeline = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("clustering", model),
        ]
    )
    pipeline.fit(x_all[columns])
    return np.asarray(pipeline.predict(x_core[columns]), dtype=int)


def run_sensitivity(
    meal_table: pd.DataFrame,
    *,
    k: int = 3,
    random_state: int = 42,
) -> tuple[pd.DataFrame, dict[str, object]]:
    core_features = build_feature_table(meal_table)
    x_core = feature_matrix(core_features)
    continuous = list(core_features.continuous_columns)
    indicators = list(core_features.indicator_columns)

    reference_labels = _fit_labels(
        x_core,
        continuous,
        indicators,
        algorithm="kmeans",
        k=k,
        clip=True,
        random_state=random_state,
    )
    core_ids = meal_id_series(core_features.frame)
    reference_frame = pd.DataFrame(
        {"meal_id": core_ids, "reference_label": reference_labels}
    )
    rows: list[dict[str, object]] = [
        {
            "variant": "reference_kmeans",
            "algorithm": "kmeans",
            "k": k,
            "n_features": len(continuous) + len(indicators),
            "n_samples_fit": len(x_core),
            "n_common": len(x_core),
            "ari_vs_reference": 1.0,
            "min_cluster_share": _min_cluster_share(reference_labels),
            "note": "core_complete, clip=True",
        }
    ]

    def add_variant(
        name: str,
        labels: np.ndarray,
        *,
        algorithm: str,
        k_value: int,
        n_features: int,
        n_samples_fit: int,
        note: str,
    ) -> None:
        rows.append(
            {
                "variant": name,
                "algorithm": algorithm,
                "k": k_value,
                "n_features": n_features,
                "n_samples_fit": n_samples_fit,
                "n_common": len(x_core),
                "ari_vs_reference": float(
                    adjusted_rand_score(reference_labels, labels)
                ),
                "min_cluster_share": _min_cluster_share(labels),
                "note": note,
            }
        )

    comparison_models = [
        ("kmeans", 2, "kmeans_k2"),
        ("gmm", 2, "gmm_k2"),
    ]
    if k != 2:
        comparison_models.append(("gmm", k, f"gmm_k{k}"))

    def add_common_variant(
        name: str,
        labels: np.ndarray,
        meal_ids: pd.Series,
        *,
        n_features: int,
        n_samples_fit: int,
        note: str,
    ) -> None:
        variant = pd.DataFrame({"meal_id": meal_ids, "variant_label": labels})
        merged = reference_frame.merge(variant, on="meal_id", how="inner")
        rows.append(
            {
                "variant": name,
                "algorithm": "kmeans",
                "k": k,
                "n_features": n_features,
                "n_samples_fit": n_samples_fit,
                "n_common": len(merged),
                "ari_vs_reference": float(
                    adjusted_rand_score(
                        merged["reference_label"], merged["variant_label"]
                    )
                ),
                "min_cluster_share": _min_cluster_share(
                    merged["variant_label"].to_numpy()
                ),
                "note": note,
            }
        )

    for algorithm, k_value, name in comparison_models:
        labels = _fit_labels(
            x_core,
            continuous,
            indicators,
            algorithm=algorithm,
            k=k_value,
            clip=True,
            random_state=random_state,
        )
        add_variant(
            name,
            labels,
            algorithm=algorithm,
            k_value=k_value,
            n_features=len(continuous) + len(indicators),
            n_samples_fit=len(x_core),
            note="same features",
        )

    for name, drop_continuous, drop_indicators in (
        ("no_sodium", {"sodium_mg_density"}, {"missing_sodium_mg_density"}),
        ("no_water", {"water_g_density"}, {"missing_water_g_density"}),
        ("no_energy", {"energy_density"}, set()),
    ):
        selected_continuous = [
            column for column in continuous if column not in drop_continuous
        ]
        selected_indicators = [
            column for column in indicators if column not in drop_indicators
        ]
        labels = _fit_labels(
            x_core,
            selected_continuous,
            selected_indicators,
            algorithm="kmeans",
            k=k,
            clip=True,
            random_state=random_state,
        )
        add_variant(
            name,
            labels,
            algorithm="kmeans",
            k_value=k,
            n_features=len(selected_continuous) + len(selected_indicators),
            n_samples_fit=len(x_core),
            note="feature ablation",
        )

    ilr_only_continuous = [
        "ilr_protein_fat_carb",
        "ilr_fat_carb",
        "log_n_products",
    ]
    ilr_only_labels = _fit_labels(
        x_core,
        ilr_only_continuous,
        [],
        algorithm="kmeans",
        k=k,
        clip=True,
        random_state=random_state,
    )
    add_variant(
        "ilr_only",
        ilr_only_labels,
        algorithm="kmeans",
        k_value=k,
        n_features=len(ilr_only_continuous),
        n_samples_fit=len(x_core),
        note="composition + complexity only",
    )

    no_clip_labels = _fit_labels(
        x_core,
        continuous,
        indicators,
        algorithm="kmeans",
        k=k,
        clip=False,
        random_state=random_state,
    )
    add_variant(
        "no_clip",
        no_clip_labels,
        algorithm="kmeans",
        k_value=k,
        n_features=len(continuous) + len(indicators),
        n_samples_fit=len(x_core),
        note="no robust-z clipping",
    )

    relaxed_features = build_feature_table(
        meal_table,
        require_core_complete=False,
        impute_core=True,
    )
    x_relaxed = feature_matrix(relaxed_features)
    relaxed_labels = _fit_on_all_predict_core(
        x_relaxed,
        x_core,
        continuous,
        indicators,
        k=k,
        random_state=random_state,
    )
    add_variant(
        "relaxed_all_meals",
        relaxed_labels,
        algorithm="kmeans",
        k_value=k,
        n_features=len(continuous) + len(indicators),
        n_samples_fit=len(x_relaxed),
        note=(
            "all meals, median core imputation; "
            f"imputed_core={relaxed_features.n_imputed_core}"
        ),
    )

    if PRODUCT_TABLE_PATH.exists():
        products = pd.read_csv(PRODUCT_TABLE_PATH)
        products["meal_id"] = meal_id_series(products)
        mrp_ids = set(
            products.loc[products["product"].eq("meal_replacement_powder"), "meal_id"]
        )
        no_mrp_table = meal_table[
            ~meal_id_series(meal_table).isin(mrp_ids)
        ].reset_index(drop=True)
        no_mrp_features = build_feature_table(no_mrp_table)
        x_no_mrp = feature_matrix(no_mrp_features)
        no_mrp_labels = _fit_labels(
            x_no_mrp,
            continuous,
            indicators,
            algorithm="kmeans",
            k=k,
            clip=True,
            random_state=random_state,
        )
        add_common_variant(
            "no_meal_replacement",
            no_mrp_labels,
            meal_id_series(no_mrp_features.frame),
            n_features=len(continuous) + len(indicators),
            n_samples_fit=len(x_no_mrp),
            note=f"excluded {len(mrp_ids)} meal_replacement_powder meals",
        )

    table = pd.DataFrame(rows)
    metadata = {
        "reference": "core_complete, K-Means, clip=True",
        "k": k,
        "random_state": random_state,
        "n_core": len(x_core),
        "n_relaxed": len(x_relaxed),
        "n_imputed_core": relaxed_features.n_imputed_core,
        "n_dropped_relaxed": relaxed_features.n_dropped,
    }
    return table, metadata


def _md_table(table: pd.DataFrame) -> str:
    columns = list(table.columns)
    lines = [
        "| " + " | ".join(str(column) for column in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for _, row in table.iterrows():
        values = [
            f"{value:.3f}" if isinstance(value, (float, np.floating)) else str(value)
            for value in row
        ]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sensitivity-анализ кластеров")
    parser.add_argument("--meal-table", type=Path, default=MEAL_TABLE_PATH)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR / "sensitivity")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args(argv)

    meal_table = pd.read_csv(args.meal_table)
    table, metadata = run_sensitivity(
        meal_table,
        k=args.k,
        random_state=args.random_state,
    )
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(reports_dir / "sensitivity.csv", index=False, encoding="utf-8")
    (reports_dir / "sensitivity_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (reports_dir / "sensitivity_report.md").write_text(
        "\n".join(
            [
                "# Sensitivity-анализ кластеризации",
                "",
                f"Reference: {metadata['reference']}, K={metadata['k']}.",
                "",
                _md_table(table),
                "",
                "## Как читать",
                "",
                "- `ari_vs_reference` — совпадение с основным решением на "
                "`core_complete`-выборке.",
                "- `min_cluster_share` — минимальная доля кластера; ниже 5 % "
                "решение вырождается.",
                "- `relaxed_all_meals` — чувствительность к отбору только "
                "полных приёмов; ядро импутировано медианой.",
                "- `no_sodium`, `no_water`, `no_energy`, `ilr_only` — проверка, "
                "не держится ли решение на одном признаке.",
                "",
                "## Решение",
                "",
                "Решение принимается по совокупности ARI, размера кластеров и "
                "интерпретируемости. Если ablation резко снижает ARI, текущий K "
                "не защищается; если `relaxed_all_meals` даёт низкий ARI, "
                "присутствует selection bias по полноте профиля.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(table.to_string(index=False))
    print(f"Отчёт: {reports_dir / 'sensitivity_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
