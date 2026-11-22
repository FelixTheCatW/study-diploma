"""Правила рекомендаций по кластеру и риск-флагам.

Рекомендации шаблонные и информационные: они не являются медицинским
заключением и не подтверждены экспертной валидацией.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Recommendation:
    code: str
    title: str
    action: str
    rationale: str
    priority: int
    kind: str = "action"


RULES: dict[str, Recommendation] = {
    "low_fiber": Recommendation(
        code="low_fiber",
        title="Добавить продукты с клетчаткой",
        action="Добавьте порцию овощей, салат или бобовые к этому приёму.",
        rationale="Клетчатка ниже 25-го перцентиля reference-выборки.",
        priority=10,
    ),
    "low_protein": Recommendation(
        code="low_protein",
        title="Добавить источник белка",
        action="Добавьте яйцо, рыбу, птицу, тофу или бобовые.",
        rationale="Белок ниже 25-го перцентиля reference-выборки.",
        priority=20,
    ),
    "high_saturated_fat": Recommendation(
        code="high_saturated_fat",
        title="Заменить часть насыщенных жиров",
        action="Замените часть жирного продукта на рыбу, птицу без кожи "
        "или растительный источник.",
        rationale="Насыщенные жиры выше 75-го перцентиля reference-выборки.",
        priority=30,
    ),
    "high_sodium": Recommendation(
        code="high_sodium",
        title="Снизить натрий",
        action="Уменьшите соусы, солёные и переработанные продукты; "
        "проверьте состав продукта.",
        rationale="Натрий выше 75-го перцентиля reference-выборки.",
        priority=40,
    ),
    "high_sugars": Recommendation(
        code="high_sugars",
        title="Снизить сахара",
        action="Замените сладкий продукт на фрукт или несладкий вариант.",
        rationale="Сахара выше 75-го перцентиля reference-выборки.",
        priority=50,
    ),
}

NO_DEVIATION = Recommendation(
    code="no_deviation",
    title="Существенных отклонений по правилам нет",
    action="Сохраните текущий состав; добавьте овощи, если их обычно мало.",
    rationale="Ни один риск-флаг не сработал.",
    priority=100,
)

HIGH_ENERGY_DENSITY = Recommendation(
    code="high_energy_density",
    title="Снизить энергоплотность",
    action="Добавьте овощи или уменьшите долю жирных соусов, чтобы снизить "
    "калорийность на 100 г.",
    rationale="Приём попал в высокоэнергетический кластер 0.",
    priority=15,
)

GENERAL_BALANCE = Recommendation(
    code="general_balance",
    title="Проверить баланс приёма",
    action="Добавьте овощи и источник белка, если их нет в этом приёме.",
    rationale="Явных флагов нет; это общая проверка баланса, не диагноз.",
    priority=90,
)

PRODUCT_SPECIFIC_WARNING = Recommendation(
    code="product_specific",
    title="Кластер 0 ограниченно интерпретируем",
    action="Учитывайте: кластер 0 в основном сформирован "
    "meal_replacement_powder; вывод по нему не переносится на обычные блюда.",
    rationale="Кластер 0 product-specific; это не общий тип питания.",
    priority=5,
    kind="warning",
)


def recommend(
    flags: Mapping[str, object],
    *,
    cluster: int | None = None,
    cluster_scope: str | None = None,
    max_items: int = 3,
) -> list[Recommendation]:
    """Вернуть до ``max_items`` действий и предупреждения по кластеру."""
    actions = [rule for flag, rule in RULES.items() if bool(flags.get(flag, False))]
    actions.sort(key=lambda item: item.priority)
    selected = actions[:max_items]
    if not selected:
        selected = (
            [HIGH_ENERGY_DENSITY, GENERAL_BALANCE]
            if cluster == 0
            else [NO_DEVIATION, GENERAL_BALANCE]
        )
    selected = selected[:max_items]

    result = list(selected)
    if cluster_scope == "product_specific":
        result.append(PRODUCT_SPECIFIC_WARNING)
    return result


def rules_table() -> pd.DataFrame:
    rows = [
        {
            "code": rule.code,
            "title": rule.title,
            "action": rule.action,
            "rationale": rule.rationale,
            "priority": rule.priority,
            "kind": rule.kind,
        }
        for rule in [
            *RULES.values(),
            NO_DEVIATION,
            HIGH_ENERGY_DENSITY,
            GENERAL_BALANCE,
            PRODUCT_SPECIFIC_WARNING,
        ]
    ]
    return pd.DataFrame(rows).sort_values("priority").reset_index(drop=True)
