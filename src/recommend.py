"""Генерация отчёта по рекомендациям и пороговым значениям флагов."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import MEAL_TABLE_PATH, REPORTS_DIR
from src.flags import compute_thresholds, meal_flags, save_thresholds
from src.recommendations import Recommendation, recommend, rules_table


def _md_table(table: pd.DataFrame, float_format: str = ".3f") -> str:
    columns = list(table.columns)
    lines = [
        "| " + " | ".join(str(column) for column in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for _, row in table.iterrows():
        values: list[str] = []
        for value in row:
            if isinstance(value, float):
                values.append(f"{value:{float_format}}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _scope_map(path: Path) -> dict[int, dict[str, str]]:
    if not path.exists():
        return {}
    table = pd.read_csv(path)
    return {
        int(row["cluster"]): {
            "name": str(row.get("cluster_name", f"cluster {row['cluster']}")),
            "scope": str(row.get("scope", "")),
        }
        for row in table.to_dict(orient="records")
    }


def _row_recommendations(
    flags: dict[str, object],
    cluster: int,
    scope: str | None,
) -> tuple[list[Recommendation], list[Recommendation]]:
    items = recommend(flags, cluster=cluster, cluster_scope=scope)
    actions = [item for item in items if item.kind == "action"]
    warnings = [item for item in items if item.kind == "warning"]
    return actions, warnings


def build_recommendations(
    *,
    meal_table_path: Path = MEAL_TABLE_PATH,
    examples_path: Path = REPORTS_DIR / "interpretation" / "cluster_examples.csv",
    cluster_flags_path: Path = REPORTS_DIR / "interpretation" / "cluster_flags.csv",
    scope_path: Path = REPORTS_DIR / "interpretation" / "cluster_scope.csv",
    reports_dir: Path = REPORTS_DIR / "recommendations",
) -> dict[str, Path]:
    meal_table = pd.read_csv(meal_table_path)
    core = meal_table[meal_table["core_complete"].astype(bool)].copy()
    thresholds = compute_thresholds(core)

    reports_dir.mkdir(parents=True, exist_ok=True)
    thresholds_path = reports_dir / "flag_thresholds.json"
    save_thresholds(thresholds, thresholds_path)

    rules_path = reports_dir / "rule_table.csv"
    rules_table().to_csv(rules_path, index=False, encoding="utf-8")

    scope = _scope_map(scope_path)
    cluster_flags = pd.read_csv(cluster_flags_path)
    cluster_rows: list[dict[str, object]] = []
    for row in cluster_flags.to_dict(orient="records"):
        cluster = int(row["cluster"])
        cluster_scope = scope.get(cluster, {}).get("scope") or None
        cluster_name = scope.get(cluster, {}).get("name", f"cluster {cluster}")
        flags = {
            key: bool(row.get(key, False))
            for key in (
                "high_saturated_fat",
                "high_sugars",
                "high_sodium",
                "low_fiber",
                "low_protein",
            )
            if float(row.get(key, 0.0)) >= 0.5
        }
        actions, warnings = _row_recommendations(flags, cluster, cluster_scope)
        for item in [*actions, *warnings]:
            cluster_rows.append(
                {
                    "cluster": cluster,
                    "cluster_name": cluster_name,
                    "scope": cluster_scope or "",
                    "code": item.code,
                    "title": item.title,
                    "action": item.action,
                    "kind": item.kind,
                    "priority": item.priority,
                    "trigger_share": float(row.get(item.code, row.get("n_flags", 0.0)))
                    if item.code in row
                    else None,
                }
            )
    cluster_table = pd.DataFrame(cluster_rows)
    cluster_table_path = reports_dir / "cluster_recommendations.csv"
    cluster_table.to_csv(cluster_table_path, index=False, encoding="utf-8")

    examples = pd.read_csv(examples_path)
    examples["meal_id"] = examples["meal_id"].astype(str)
    flag_columns = [
        "high_saturated_fat",
        "high_sugars",
        "high_sodium",
        "low_fiber",
        "low_protein",
    ]
    flags = meal_flags(examples, thresholds)
    examples = examples.merge(
        flags[["meal_id", *flag_columns, "missing_input", "n_flags"]],
        on="meal_id",
        how="left",
    )
    example_rows: list[dict[str, object]] = []
    for row in examples.to_dict(orient="records"):
        cluster = int(row["cluster"])
        cluster_scope = scope.get(cluster, {}).get("scope") or None
        flag_values = {key: bool(row.get(key, False)) for key in flag_columns}
        actions, warnings = _row_recommendations(flag_values, cluster, cluster_scope)
        result = {
            "cluster": cluster,
            "cluster_name": row.get("cluster_name", ""),
            "scope": cluster_scope or "",
            "example_type": row.get("example_type", ""),
            "meal_id": row.get("meal_id", ""),
            "meal": row.get("meal", ""),
            "products": row.get("products", ""),
            **{flag: flag_values[flag] for flag in flag_columns},
            "warnings": "; ".join(item.title for item in warnings),
        }
        for index, item in enumerate(actions[:3], start=1):
            result[f"recommendation_{index}"] = item.action
        example_rows.append(result)
    examples_table = pd.DataFrame(example_rows)
    for index in range(1, 4):
        column = f"recommendation_{index}"
        if column not in examples_table.columns:
            examples_table[column] = ""
    examples_path_out = reports_dir / "examples_with_recommendations.csv"
    examples_table.to_csv(examples_path_out, index=False, encoding="utf-8")

    status_path = reports_dir / "status.md"
    status_path.write_text(
        "\n".join(
            [
                "# Рекомендации: статус",
                "",
                "Правила rule-based, без свободного LLM. Экспертная валидация "
                "кластеров не проведена, Cohen's kappa отсутствует.",
                "",
                "Рекомендации и флаги являются информационными и не являются "
                "медицинским заключением. До kappa >= 0,5 продуктовые "
                "утверждения не выносятся.",
                "",
                "Пороговые значения флагов: `flag_thresholds.json`; они "
                "рассчитаны на `core_complete` reference-выборке.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report_lines = [
        "# Правила рекомендаций",
        "",
        "Источник флагов: `flag_thresholds.json`; правила не являются "
        "медицинскими рекомендациями. Экспертная валидация не проведена.",
        "",
        "## Таблица правил",
        "",
        _md_table(rules_table()),
        "",
        "## Рекомендации по кластерам",
        "",
        _md_table(
            cluster_table[["cluster", "cluster_name", "scope", "code", "title", "kind"]]
        )
        if not cluster_table.empty
        else "Нет кластерных рекомендаций.",
        "",
        "## Примеры",
        "",
        _md_table(
            examples_table[
                [
                    "cluster",
                    "example_type",
                    "meal",
                    "products",
                    "recommendation_1",
                    "recommendation_2",
                    "warnings",
                ]
            ].head(30)
        ),
        "",
        "## Ограничения",
        "",
        "- Флаги сравнивают приём с перцентилями reference, а не с нормами.",
        "- Кластер 0 продукт-специфичный; его предупреждение не является "
        "общим выводом о рационе.",
        "- Пропуски нутриентов не трактуются как низкие значения.",
        "- 2–3 рекомендации формируются детерминированно по правилам.",
        "",
        "## Артефакты",
        "",
        "- `rule_table.csv`, `cluster_recommendations.csv`;",
        "- `examples_with_recommendations.csv`, `flag_thresholds.json`;",
        "- `status.md`.",
        "",
    ]
    report_path = reports_dir / "recommendations_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return {
        "report": report_path,
        "rules": rules_path,
        "clusters": cluster_table_path,
        "examples": examples_path_out,
        "thresholds": thresholds_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Отчёт по рекомендациям")
    parser.add_argument("--meal-table", type=Path, default=MEAL_TABLE_PATH)
    parser.add_argument(
        "--examples",
        type=Path,
        default=REPORTS_DIR / "interpretation" / "cluster_examples.csv",
    )
    parser.add_argument(
        "--cluster-flags",
        type=Path,
        default=REPORTS_DIR / "interpretation" / "cluster_flags.csv",
    )
    parser.add_argument(
        "--scope",
        type=Path,
        default=REPORTS_DIR / "interpretation" / "cluster_scope.csv",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR / "recommendations",
    )
    args = parser.parse_args(argv)
    paths = build_recommendations(
        meal_table_path=args.meal_table,
        examples_path=args.examples,
        cluster_flags_path=args.cluster_flags,
        scope_path=args.scope,
        reports_dir=args.reports_dir,
    )
    print(
        json.dumps(
            {key: str(value) for key, value in paths.items()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
