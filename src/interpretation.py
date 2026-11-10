"""Интерпретация кластеров: карточки, примеры, распределения, флаги.

Запуск:
    uv run python -m src.interpretation
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from src.clustering import cluster_profiles, fit_final_pipeline
from src.config import (
    MEAL_TABLE_PATH,
    PRODUCT_TABLE_PATH,
    REPORTS_DIR,
)
from src.expert_validation import SAMPLE_COLUMNS, build_expert_pack
from src.features import build_feature_table, feature_matrix
from src.flags import cluster_flag_summary, meal_flags
from src.keys import meal_id_series

DEFAULT_METADATA = REPORTS_DIR / "clustering" / "run_metadata.json"


def load_selected(metadata_path: Path) -> dict[str, object]:
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        selected = metadata.get("selected", {})
        return {
            "algorithm": str(selected.get("algorithm", "kmeans")),
            "k": int(selected.get("k", 3)),
            "random_state": int(metadata.get("random_state", 42)),
            "metadata": metadata,
        }
    return {"algorithm": "kmeans", "k": 3, "random_state": 42, "metadata": {}}


def _products_by_meal(product_table_path: Path) -> pd.DataFrame:
    if not product_table_path.exists():
        return pd.DataFrame(columns=["meal_id", "products"])
    products = pd.read_csv(product_table_path)
    products["meal_id"] = meal_id_series(products)
    grouped = (
        products.groupby("meal_id")["product"]
        .agg(
            lambda values: ", ".join(sorted({str(value) for value in values.dropna()}))
        )
        .reset_index()
        .rename(columns={"product": "products"})
    )
    return grouped


def _distances(pipeline, x: pd.DataFrame, labels: np.ndarray) -> np.ndarray:
    preprocessing = pipeline.named_steps["preprocessing"]
    model = pipeline.named_steps["clustering"]
    transformed = np.asarray(preprocessing.transform(x))
    centers = getattr(model, "cluster_centers_", None)
    if centers is None:
        centers = getattr(model, "means_", None)
    if centers is None:
        return np.zeros(len(x), dtype=float)
    return np.linalg.norm(transformed - centers[labels], axis=1)


def _suggest_name(z_scores: dict[str, float]) -> str:
    energy = z_scores.get("energy_density", 0.0)
    fiber = z_scores.get("fiber_g_density", 0.0)
    if energy > 0.8 and fiber < -0.2:
        return "высокоэнергетический белково-жировой"
    if fiber > 0.8 and energy < -0.5:
        return "растительный высококлетчаточный"
    return "смешанный/типичный"


def _cluster_names(profiles: pd.DataFrame) -> dict[int, str]:
    continuous = profiles[~profiles["feature"].str.startswith("missing_")]
    names: dict[int, str] = {}
    for cluster, group in continuous.groupby("cluster"):
        z_scores = dict(zip(group["feature"], group["z_score"], strict=True))
        names[int(cluster)] = _suggest_name(z_scores)
    return names


def _top_features(profiles: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    continuous = profiles[~profiles["feature"].str.startswith("missing_")].copy()
    continuous["abs_z"] = continuous["z_score"].abs()
    return (
        continuous.sort_values(["cluster", "abs_z"], ascending=[True, False])
        .groupby("cluster", sort=True)
        .head(n)
        .reset_index(drop=True)
    )


def _meal_distribution(sample: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        sample.groupby("cluster", as_index=False)
        .agg(
            n=("meal_id", "size"),
            mean_n_products=("n_products", "mean"),
            mean_energy_density=("energy_density", "mean"),
        )
        .assign(share=lambda table: table["n"] / len(sample))
    )
    meal_share = (
        pd.crosstab(sample["cluster"], sample["meal"], normalize="index")
        .reset_index()
        .rename_axis(columns=None)
    )
    for meal in ("breakfast", "lunch", "supper"):
        if meal not in meal_share.columns:
            meal_share[meal] = 0.0
    return grouped.merge(
        meal_share[["cluster", "breakfast", "lunch", "supper"]],
        on="cluster",
        how="left",
    )


def _product_counts(sample: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for cluster, group in sample.groupby("cluster", sort=True):
        counts: Counter[str] = Counter()
        for text in group["products"].astype(str):
            for product in text.split(", "):
                product = product.strip()
                if product:
                    counts[product] += 1
        for product, count in counts.most_common(n):
            rows.append(
                {
                    "cluster": int(cluster),
                    "product": product,
                    "n_meals": count,
                    "share": count / len(group),
                }
            )
    return pd.DataFrame(rows)


def _cluster_scope(
    profiles: pd.DataFrame,
    products: pd.DataFrame,
    names: dict[int, str],
) -> pd.DataFrame:
    continuous = profiles[~profiles["feature"].str.startswith("missing_")]
    rows: list[dict[str, object]] = []
    for cluster, group in continuous.groupby("cluster", sort=True):
        top = (
            products[products["cluster"] == cluster]
            .sort_values("share", ascending=False)
            .head(1)
        )
        top_product = str(top["product"].iloc[0]) if not top.empty else ""
        top_share = float(top["share"].iloc[0]) if not top.empty else 0.0
        max_abs_z = float(group["z_score"].abs().max())
        if top_share >= 0.5:
            scope = "product_specific"
        elif max_abs_z < 0.3:
            scope = "mixed"
        else:
            scope = "pattern"
        rows.append(
            {
                "cluster": int(cluster),
                "cluster_name": names[int(cluster)],
                "scope": scope,
                "top_product": top_product,
                "top_product_share": top_share,
                "max_abs_z": max_abs_z,
            }
        )
    return pd.DataFrame(rows)


def _example_rows(
    sample: pd.DataFrame,
    cluster: int,
    *,
    random_state: int,
) -> list[pd.DataFrame]:
    group = (
        sample[sample["cluster"] == cluster]
        .sort_values("distance")
        .drop_duplicates("products")
        .reset_index(drop=True)
    )
    if group.empty:
        return []
    nearest = group.head(5).assign(example_type="nearest_centroid")
    boundary = (
        group.sort_values("distance", ascending=False)
        .head(5)
        .assign(example_type="boundary")
    )
    random_count = min(10, len(group))
    random = group.sample(random_count, random_state=random_state + cluster).assign(
        example_type="random"
    )
    return [nearest, boundary, random]


def _md_table(table: pd.DataFrame, float_format: str = ".3f") -> str:
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


def _scope_line(scope: pd.DataFrame, cluster: int) -> str:
    row = scope[scope["cluster"] == cluster]
    if row.empty:
        return "Тип: не определён."
    item = row.iloc[0]
    labels = {
        "pattern": "выраженный паттерн",
        "mixed": "смешанный/типичный",
        "product_specific": "продукт-специфичный",
    }
    text = f"Тип: {labels.get(str(item['scope']), item['scope'])}"
    if item["scope"] == "product_specific":
        text += f"; {item['top_product_share']:.0%} приёмов содержат `{item['top_product']}`"
    return text + "."


def _write_cards(
    path: Path,
    *,
    names: dict[int, str],
    distribution: pd.DataFrame,
    top: pd.DataFrame,
    flags: pd.DataFrame,
    examples: pd.DataFrame,
    products: pd.DataFrame,
    scope: pd.DataFrame,
) -> None:
    lines = ["# Карточки кластеров", ""]
    for cluster in sorted(names):
        row = distribution[distribution["cluster"] == cluster].iloc[0]
        cluster_top = top[top["cluster"] == cluster]
        cluster_flags = flags[flags["cluster"] == cluster]
        cluster_examples = examples[
            (examples["cluster"] == cluster)
            & (examples["example_type"] == "nearest_centroid")
        ]
        lines.extend(
            [
                f"## Кластер {cluster} — {names[cluster]}",
                "",
                f"- Размер: {int(row['n'])} ({row['share']:.1%}).",
                f"- Приёмы: завтрак {row['breakfast']:.1%}, обед {row['lunch']:.1%}, "
                f"ужин {row['supper']:.1%}.",
                f"- Среднее число продуктов: {row['mean_n_products']:.2f}; "
                f"энергоплотность: {row['mean_energy_density']:.1f} ккал/100 г.",
                "",
                _scope_line(scope, cluster),
                "",
                "Отличия от общего среднего:",
                "",
                _md_table(
                    cluster_top[["feature", "cluster_mean", "overall_mean", "z_score"]]
                ),
                "",
            ]
        )
        if not cluster_flags.empty:
            flag_columns = [
                column
                for column in cluster_flags.columns
                if column.startswith(("high_", "low_"))
            ]
            lines.extend(
                [
                    "Доля приёмов с флагами:",
                    "",
                    _md_table(
                        cluster_flags[["n", "missing_input", *flag_columns]],
                        float_format=".3f",
                    ),
                    "",
                ]
            )
        cluster_products = products[products["cluster"] == cluster].head(5)
        if not cluster_products.empty:
            lines.extend(
                [
                    "Частые продукты:",
                    "",
                    _md_table(cluster_products[["product", "n_meals", "share"]]),
                    "",
                ]
            )
        lines.extend(["Примеры ближайших к центроиду:", ""])
        for _, example in cluster_examples.head(3).iterrows():
            lines.append(
                f"- `{example['meal_id']}` ({example['meal']}): "
                f"{example['products']}; энергоплотность "
                f"{example['energy_density']:.1f} ккал/100 г."
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Интерпретация кластеров")
    parser.add_argument("--meal-table", type=Path, default=MEAL_TABLE_PATH)
    parser.add_argument("--product-table", type=Path, default=PRODUCT_TABLE_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument(
        "--reports-dir", type=Path, default=REPORTS_DIR / "interpretation"
    )
    parser.add_argument(
        "--expert-dir",
        type=Path,
        default=REPORTS_DIR / "expert_validation",
    )
    parser.add_argument("--algorithm", type=str, default=None)
    parser.add_argument("--k", type=int, default=None)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--expert-per-cluster", type=int, default=30)
    parser.add_argument("--skip-expert", action="store_true")
    args = parser.parse_args(argv)

    selected = load_selected(args.metadata)
    algorithm = args.algorithm or str(selected["algorithm"])
    k = args.k if args.k is not None else int(selected["k"])
    random_state = args.random_state

    meal_table = pd.read_csv(args.meal_table)
    features = build_feature_table(meal_table)
    x = feature_matrix(features)
    pipeline, labels = fit_final_pipeline(
        x,
        features.continuous_columns,
        features.indicator_columns,
        algorithm=algorithm,
        k=k,
        random_state=random_state,
    )

    profiles, sizes = cluster_profiles(
        features.frame,
        labels,
        features.continuous_columns,
        features.indicator_columns,
    )
    names = _cluster_names(profiles)
    top = _top_features(profiles)
    distance = _distances(pipeline, x, labels)

    sample = features.frame.copy()
    sample["meal_id"] = meal_id_series(sample)
    sample["cluster"] = labels
    sample["cluster_name"] = sample["cluster"].map(names)
    sample["distance"] = np.round(distance, 10)
    sample = sample.merge(
        _products_by_meal(args.product_table), on="meal_id", how="left"
    )
    sample["products"] = sample["products"].fillna("")

    raw_columns = [
        column
        for column in SAMPLE_COLUMNS
        if column in meal_table.columns and column not in sample.columns
    ]
    if raw_columns:
        raw = meal_table.copy()
        raw["meal_id"] = meal_id_series(raw)
        sample = sample.merge(raw[["meal_id", *raw_columns]], on="meal_id", how="left")

    distribution = _meal_distribution(sample)
    product_counts = _product_counts(sample)
    scope = _cluster_scope(profiles, product_counts, names)

    core_meal_table = meal_table[meal_table["core_complete"].astype(bool)].copy()
    flags = meal_flags(core_meal_table)
    labels_frame = sample[["meal_id", "cluster"]].copy()
    flag_summary = cluster_flag_summary(flags, labels_frame)

    examples_frames: list[pd.DataFrame] = []
    for cluster in sorted(names):
        examples_frames.extend(
            _example_rows(sample, cluster, random_state=random_state)
        )
    examples = pd.concat(examples_frames, ignore_index=True)
    example_columns = [
        "cluster",
        "cluster_name",
        "example_type",
        "distance",
        "meal_id",
        "id",
        "date",
        "meal",
        "products",
        "energy_density",
        "n_products",
        "protein_g_mean_per_100kcal",
        "fat_g_mean_per_100kcal",
        "carbohydrates_g_mean_per_100kcal",
        "fiber_g_mean_per_100kcal",
        "sugars_g_mean_per_100kcal",
        "saturated_fat_g_mean_per_100kcal",
        "sodium_mg_mean_per_100kcal",
    ]
    examples = examples[
        [column for column in example_columns if column in examples.columns]
    ]

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    profiles.assign(cluster_name=profiles["cluster"].map(names)).to_csv(
        reports_dir / "cluster_profiles.csv", index=False, encoding="utf-8"
    )
    top.assign(cluster_name=top["cluster"].map(names)).to_csv(
        reports_dir / "cluster_top_features.csv", index=False, encoding="utf-8"
    )
    distribution.assign(cluster_name=distribution["cluster"].map(names)).to_csv(
        reports_dir / "cluster_distribution.csv", index=False, encoding="utf-8"
    )
    flag_summary.to_csv(
        reports_dir / "cluster_flags.csv", index=False, encoding="utf-8"
    )
    product_counts.assign(cluster_name=product_counts["cluster"].map(names)).to_csv(
        reports_dir / "cluster_products.csv", index=False, encoding="utf-8"
    )
    scope.to_csv(reports_dir / "cluster_scope.csv", index=False, encoding="utf-8")
    examples.to_csv(reports_dir / "cluster_examples.csv", index=False, encoding="utf-8")
    sizes.assign(cluster_name=sizes["cluster"].map(names)).to_csv(
        reports_dir / "cluster_sizes.csv", index=False, encoding="utf-8"
    )
    _write_cards(
        reports_dir / "cluster_cards.md",
        names=names,
        distribution=distribution,
        top=top,
        flags=flag_summary,
        examples=examples,
        products=product_counts,
        scope=scope,
    )

    expert_paths: dict[str, Path] = {}
    if not args.skip_expert:
        expert_sample = sample[
            [
                column
                for column in [
                    *SAMPLE_COLUMNS,
                    "cluster",
                    "cluster_name",
                    "distance",
                ]
                if column in sample.columns
            ]
        ].copy()
        expert_paths = build_expert_pack(
            expert_sample,
            args.expert_dir,
            n_per_cluster=args.expert_per_cluster,
            random_state=random_state,
        )

    dominant_lines = [
        f"- Кластер {int(row.cluster)}: {row.share:.0%} приёмов содержат "
        f"`{row.product}`; это может быть продукт-специфичный паттерн, "
        "а не общий тип питания."
        for row in product_counts[product_counts["share"] >= 0.5].itertuples()
    ]

    report_lines = [
        "# Интерпретация кластеров",
        "",
        f"Выбрано: `{algorithm}`, `K={k}`; приёмов: {len(sample)}.",
        "",
        "## Названия и размеры",
        "",
        _md_table(
            distribution.assign(cluster_name=distribution["cluster"].map(names))[
                [
                    "cluster",
                    "cluster_name",
                    "n",
                    "share",
                    "breakfast",
                    "lunch",
                    "supper",
                    "mean_n_products",
                    "mean_energy_density",
                ]
            ]
        ),
        "",
        "## Финальное решение",
        "",
        f"Основная модель: `{algorithm}`, `K={k}`, {len(features.feature_columns)} признаков, выборка "
        f"`core_complete` ({len(sample)} приёмов), clip ±5. Решение по "
        "кластерам:",
        "",
        _md_table(
            scope[
                [
                    "cluster",
                    "cluster_name",
                    "scope",
                    "top_product",
                    "top_product_share",
                    "max_abs_z",
                ]
            ]
        ),
        "",
        "Кластер 0 — продукт-специфичный: доминирует "
        "`meal_replacement_powder`; его нельзя обобщать как общий тип питания. "
        "Кластер 1 — смешанный/типичный, кластер 2 — выраженный растительный "
        "паттерн. Экспертная валидация не проведена, поэтому продуктовые "
        "утверждения заблокированы.",
        "",
        "## Топ отличий",
        "",
        _md_table(
            top[["cluster", "feature", "cluster_mean", "overall_mean", "z_score"]]
        ),
        "",
        "## Флаги по кластерам",
        "",
        _md_table(flag_summary, float_format=".3f"),
        "",
        "## Экспертная валидация",
        "",
        "Статус: пакет подготовлен, разметка не проведена."
        if expert_paths
        else "Статус: пакет не создавался.",
        "",
        "Порог: Cohen's kappa >= 0.5 для exploratory, >= 0.6 для продуктового вывода.",
        "",
        "## Sensitivity",
        "",
        "См. `reports/sensitivity/sensitivity_report.md`: ablation, K=2, GMM, "
        "clip и relaxed_all_meals.",
        "",
        "## Ограничения",
        "",
        "- Названия кластеров предварительные и требуют экспертной проверки.",
        "- Кластер, близкий к среднему, интерпретируется как смешанный, а не как паттерн.",
        "- Флаги описательные: сравнение с перцентилями выборки, не с медицинскими нормами.",
        "- Пропуски не заменяются нулём; при неполном профиле флаги не выставляются.",
        "- Если один продукт занимает большую долю кластера, это может быть "
        "артефакт ограниченного каталога; см. `cluster_products.csv`.",
        *dominant_lines,
        "",
        "## Артефакты",
        "",
        "- `cluster_cards.md`, `cluster_examples.csv`, `cluster_distribution.csv`;",
        "- `cluster_profiles.csv`, `cluster_top_features.csv`, `cluster_flags.csv`;",
        "- `cluster_products.csv`, `cluster_scope.csv`, `decision.md`;",
        "- `reports/expert_validation/`.",
        "",
    ]
    (reports_dir / "interpretation_report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )
    decision_lines = [
        "# Решение по кластерам (неделя 4)",
        "",
        f"- Основная модель: `{algorithm}`, `K={k}`.",
        f"- Выборка: {len(sample)} приёмов с `core_complete`; {len(features.feature_columns)} признаков; clip ±5.",
        "- K=3 сохраняется как baseline: кластер 0 — продукт-специфичный "
        "(`meal_replacement_powder`), кластер 1 — смешанный/типичный, "
        "кластер 2 — выраженный растительный паттерн.",
        "- `meal_replacement_powder` не удалён из основной модели в этой "
        "итерации; он вынесен в отдельную интерпретацию и не обобщается.",
        "- Экспертная валидация не проведена; продуктовые утверждения "
        "заблокированы до kappa >= 0,5 (exploratory) / 0,6 (product).",
        "- Sensitivity: см. `reports/sensitivity/sensitivity_report.md`; "
        "без clip и на неполных приёмах K=3 вырождается.",
        "",
    ]
    (reports_dir / "decision.md").write_text(
        "\n".join(decision_lines), encoding="utf-8"
    )
    print(f"Кластеры: {names}")
    print(f"Отчёты: {reports_dir}")
    if expert_paths:
        print(f"Экспертная выборка: {expert_paths['template']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
