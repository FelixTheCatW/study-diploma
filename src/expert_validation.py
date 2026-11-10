"""Пакет экспертной валидации кластеров и расчёт agreement.

Разметка анонимная: эксперт видит приём и нутриенты, но не номер кластера.
Ключ соответствия хранится отдельно и не передаётся эксперту.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from src.config import REPORTS_DIR

SAMPLE_COLUMNS = [
    "sample_id",
    "meal_id",
    "id",
    "date",
    "meal",
    "products",
    "energy_kcal_mean_per_100g",
    "protein_g_mean_per_100kcal",
    "fat_g_mean_per_100kcal",
    "carbohydrates_g_mean_per_100kcal",
    "fiber_g_mean_per_100kcal",
    "sugars_g_mean_per_100kcal",
    "saturated_fat_g_mean_per_100kcal",
    "sodium_mg_mean_per_100kcal",
    "n_products",
]


def _band_labels(count: int) -> list[str]:
    labels = ["near_centroid", "middle", "boundary"]
    base, remainder = divmod(count, len(labels))
    result: list[str] = []
    for index, label in enumerate(labels):
        result.extend([label] * (base + (1 if index < remainder else 0)))
    return result


def build_expert_pack(
    sample: pd.DataFrame,
    output_dir: str | Path,
    *,
    n_per_cluster: int = 30,
    random_state: int = 42,
) -> dict[str, Path]:
    """Собрать стратифицированную выборку и шаблон разметки.

    ``sample`` должен содержать ``meal_id``, ``cluster``, ``distance`` и
    колонки из ``SAMPLE_COLUMNS``. В файл для эксперта не попадают cluster,
    distance и confidence band.
    """
    required = {
        "meal_id",
        "cluster",
        "distance",
        *(set(SAMPLE_COLUMNS) - {"sample_id"}),
    }
    missing = sorted(required - set(sample.columns))
    if missing:
        raise ValueError(f"В выборке нет колонок: {missing}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(random_state)
    selected: list[pd.DataFrame] = []

    for _cluster, group in sample.groupby("cluster", sort=True):
        ordered = group.sort_values("distance").reset_index(drop=True)
        count = min(n_per_cluster, len(ordered))
        bands = _band_labels(count)
        parts = np.array_split(np.arange(len(ordered)), 3)
        for band, part_indices in zip(
            ["near_centroid", "middle", "boundary"], parts, strict=True
        ):
            take = bands.count(band)
            if take == 0 or len(part_indices) == 0:
                continue
            part = ordered.iloc[part_indices]
            indices = rng.choice(len(part), size=min(take, len(part)), replace=False)
            chosen = part.iloc[np.sort(indices)].copy()
            chosen["confidence_band"] = band
            selected.append(chosen)

    if not selected:
        raise ValueError("Не удалось собрать ни одного приёма")
    pack = pd.concat(selected, ignore_index=True)
    pack = pack.sample(frac=1.0, random_state=random_state).reset_index(drop=True)
    pack["sample_id"] = [f"S{index:03d}" for index in range(1, len(pack) + 1)]

    key = pack[
        ["sample_id", "meal_id", "cluster", "distance", "confidence_band"]
    ].copy()
    key["cluster_name"] = (
        pack["cluster_name"] if "cluster_name" in pack.columns else pack["cluster"]
    )
    key["distance"] = key["distance"].round(10)
    key.to_csv(output / "sample_key.csv", index=False, encoding="utf-8")

    sample_columns = [column for column in SAMPLE_COLUMNS if column in pack.columns]
    pack[sample_columns].to_csv(output / "sample.csv", index=False, encoding="utf-8")

    template = pack[sample_columns].copy()
    template["expert_pattern"] = ""
    template["expert_confidence"] = ""
    template["comment"] = ""
    template.to_csv(output / "label_template.csv", index=False, encoding="utf-8")

    (output / "status.md").write_text(
        "\n".join(
            [
                "# Экспертная валидация",
                "",
                "Статус: не проведена.",
                "",
                "Эксперту передаётся `label_template.csv`: без кластера, "
                "расстояния и confidence band.",
                "Ключ `sample_key.csv` не передаётся эксперту.",
                "",
                "Категории:",
                "- высокоэнергетический белково-жировой;",
                "- смешанный/типичный;",
                "- растительный высококлетчаточный;",
                "- другой;",
                "- не относится.",
                "",
                "После заполнения запустить:",
                "`uv run python -m src.expert_validation --evaluate "
                "--key reports/expert_validation/sample_key.csv "
                "--labels reports/expert_validation/label_template.csv`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_protocol(output / "protocol.md", len(pack))
    return {
        "sample": output / "sample.csv",
        "key": output / "sample_key.csv",
        "template": output / "label_template.csv",
        "protocol": output / "protocol.md",
    }


def _write_protocol(path: Path, n_samples: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# Протокол экспертной валидации",
                "",
                f"Выборка: {n_samples} приёмов, стратифицированных по кластеру "
                "и удалённости от центроида (near/middle/boundary).",
                "",
                "Эксперт не видит номер кластера, расстояние и confidence band.",
                "Нужно отнести приём к одному паттерну или указать «другой» / "
                "«не относится», оценить уверенность 1–5 и оставить комментарий.",
                "",
                "Метрики после разметки: raw agreement, Cohen's kappa, "
                "confusion matrix. Порог для exploratory-вывода: kappa >= 0.5; "
                "для уверенного продуктового вывода: kappa >= 0.6.",
                "",
                "Ограничения: выборка не является случайной по кластерам; "
                "она стратифицирована для проверки интерпретируемости. "
                "Результат не является медицинской валидацией.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def evaluate_expert_labels(
    key_path: str | Path,
    labels_path: str | Path,
    output_dir: str | Path = REPORTS_DIR / "expert_validation",
) -> dict[str, object]:
    key = pd.read_csv(key_path)
    labels = pd.read_csv(labels_path)
    required_key = {"sample_id", "cluster", "cluster_name"}
    required_labels = {"sample_id", "expert_pattern"}
    if not required_key <= set(key.columns):
        raise ValueError(
            f"В ключе нет колонок: {sorted(required_key - set(key.columns))}"
        )
    if not required_labels <= set(labels.columns):
        raise ValueError(
            f"В разметке нет колонок: {sorted(required_labels - set(labels.columns))}"
        )

    merged = key.merge(labels, on="sample_id", how="inner")
    merged = merged[merged["expert_pattern"].notna()]
    merged["expert_pattern"] = merged["expert_pattern"].astype(str).str.strip()
    merged = merged[merged["expert_pattern"] != ""]
    if merged.empty:
        raise ValueError("Нет заполненных экспертных меток")

    merged["cluster_name"] = merged["cluster_name"].astype(str)
    labels_sorted = sorted(set(merged["cluster_name"]) | set(merged["expert_pattern"]))
    matrix = confusion_matrix(
        merged["cluster_name"],
        merged["expert_pattern"],
        labels=labels_sorted,
    )
    matrix_frame = pd.DataFrame(
        matrix,
        index=[f"cluster:{label}" for label in labels_sorted],
        columns=[f"expert:{label}" for label in labels_sorted],
    ).reset_index(names="cluster")
    agreement = float((merged["cluster_name"] == merged["expert_pattern"]).mean())
    kappa = float(cohen_kappa_score(merged["cluster_name"], merged["expert_pattern"]))

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    matrix_frame.to_csv(output / "confusion_matrix.csv", index=False, encoding="utf-8")
    summary = {
        "n_labels": int(len(merged)),
        "raw_agreement": agreement,
        "cohen_kappa": kappa,
        "passes_exploratory": bool(kappa >= 0.5),
        "passes_product": bool(kappa >= 0.6),
        "categories": labels_sorted,
    }
    (output / "agreement.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "agreement.md").write_text(
        "\n".join(
            [
                "# Согласие с экспертом",
                "",
                f"- Размечено: {len(merged)}",
                f"- Raw agreement: {agreement:.3f}",
                f"- Cohen's kappa: {kappa:.3f}",
                f"- Exploratory (kappa >= 0.5): {summary['passes_exploratory']}",
                f"- Product (kappa >= 0.6): {summary['passes_product']}",
                "",
                "Confusion matrix: `confusion_matrix.csv`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Экспертная валидация кластеров")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--key", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=REPORTS_DIR / "expert_validation"
    )
    args = parser.parse_args(argv)
    if not args.evaluate:
        parser.print_help()
        return 1
    if args.key is None or args.labels is None:
        parser.error("Нужны --key и --labels")
    summary = evaluate_expert_labels(args.key, args.labels, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
