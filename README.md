# Дипломный проект: анализ пищевого поведения

Недели 2–3: загрузка, анализ, подготовка данных и исправление сопоставления
с USDA. Пропуски нутриентов не трактуются как ноль.

Проект реализует воспроизводимый конвейер `DietDiary → USDA FoodData Central`
и подготавливает три уровня данных:

1. **Продукт в приёме** — нутриенты на 100 г.
2. **Приём пищи** — средний профиль продукта, плотность на 100 ккал и полнота
   нутриентов.
3. **День пользователя** — число приёмов, средний профиль и вес.

Суммирование концентраций на 100 г по продуктам **не выполняется**: сумма
растёт с числом продуктов и смешивает паттерн с размером корзины. Вместо неё
используются средние значения, плотность на 100 ккал и отдельный признак
`n_products`.

## Структура

```
src/
  config.py            пути, нутриенты, поиск каталога USDA
  data_loader.py       CSV/Parquet: загрузка и сохранение
  data_analyzer.py     профиль датасета, пропуски, дубликаты, статистики
  data_preparer.py     продукт → приём → день
  features.py          доли БЖУ, ILR, плотности, missing-индикаторы
  preprocessing.py     медианная импутация, RobustScaler, clip выбросов
  clustering.py        K-Means, GMM, Agglomerative, метрики, устойчивость
  cluster.py           CLI кластеризации и отчётов
  analyze.py           CLI анализа датасетов
  prepare.py           CLI подготовки DietDiary + USDA
  utils/
    diary.py           разбор DietDiary
    usda.py            поиск в USDA, nutrient_id fallback, нутриенты
    product_map.py     курируемое сопоставление продукт → fdc_id
  resources/
    product_fdc_map.csv  197 продуктов: fdc_id или осознанно пусто
tests/                 pytest-тесты на синтетических данных
data/                  исходные датасеты
data/processed/        результат подготовки
reports/               профилирование, матчинг и отчёты кластеризации
```

## Данные

В `data/` лежат:

- `diet_diary.csv` — исходный дневник DietDiary (5 251 день, 611 пользователей);
- `food_data.csv` — Open Food Facts (для EDA, не для нутриентного обогащения);
- `health_fitness_dataset.csv`, `fitness_tracker_dataset.csv`,
  `daily_nutrition.csv`, `mfp-diaries.parquet` и др. — источники прошлых этапов.

Для итогового конвейера нужны `diet_diary.csv` и справочник USDA
FoodData Central. Справочник не входит в репозиторий из-за размера (~3 ГБ).
Укажите его одним из способов:

1. Скопируйте каталог в `data/FoodData_Central_csv_2026-04-30`.
2. Задайте переменную окружения `DIPLOMA_USDA_DIR`.

PowerShell:

```powershell
$env:DIPLOMA_USDA_DIR = "D:\study\ml\study-ml\data\FoodData_Central_csv_2026-04-30"
```

## Установка

Через `uv`:

```powershell
uv sync --extra dev
```

Через `pip`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

## Запуск тестов

```powershell
uv run pytest -q
```

Отдельные файлы:

```powershell
uv run pytest -q tests/test_diary.py
uv run pytest -q tests/test_usda.py
uv run pytest -q tests/test_data_preparer.py
uv run pytest -q tests/test_data_analyzer.py
```

Тесты не требуют реального USDA: справочник и дневник создаются во временных
каталогах. Parquet-тест пропускается, если `pyarrow` не установлен.

## Анализ данных

```powershell
uv run python -m src.analyze
```

По умолчанию профилируются `diet_diary`, `health_fitness`,
`daily_nutrition` и `food_data` (до 200 000 строк на датасет). Тяжёлый
`mfp_diaries` можно добавить явно:

```powershell
uv run python -m src.analyze --datasets diet_diary mfp_diaries --sample 100000
```

Отчёт сохраняется в `reports/data_profile.md`.

## Подготовка данных

```powershell
uv run python -m src.prepare --force
```

Результат:

- `data/processed/product_table.csv` — продукт в приёме + нутриенты USDA;
- `data/processed/meal_table.csv` — приём пищи;
- `data/processed/day_table.csv` — день пользователя.

Полезные параметры:

```powershell
uv run python -m src.prepare --help
uv run python -m src.prepare --usda-dir "D:\path\to\usda" --min-products 2
```

На текущих данных получено: 52 479 продуктов, 15 323 приёма, 5 249 дней,
611 пользователей и 197 уникальных продуктов. Курируемая таблица покрывает
165 продуктов и 47 118 строк (89,8 %); 32 неоднозначных названия намеренно
оставлены без матча, их нутриенты — `NaN`, а не `0`. Полное покрытие ядра
(energy + БЖУ) имеют 70,6 % приёмов; они помечены `core_complete = True` и
`is_reliable = True`. Остальные не удаляются, а получают пропуски,
`coverage_*` и `missing_*`.

## Кластеризация (неделя 3)

```powershell
uv run python -m src.cluster --bootstrap 30
```

Основная выборка — 10 817 приёмов с `core_complete = True`. Признаки:
ILR долей БЖУ, энергоплотность, плотности fiber/sugars/saturated fat/sodium/
potassium/water на 100 ккал, `log1p(n_products)` и missing-индикаторы.
Пропуски плотностей импутируются медианой внутри Pipeline; выбросы
ограничиваются в robust-z-пространстве (`clip` до ±5), иначе единичные
продукты с экстремальным натрием образуют кластеры из нескольких наблюдений.

Выбор K: максимальное K, прошедшее пороги `median ARI >= 0,75` и
`min cluster share >= 5 %`, затем лучший алгоритм при этом K. На текущих
данных выбрано `K-Means, K = 3`: размеры кластеров 1 286 / 7 574 / 1 957,
median bootstrap ARI 0,984. `GMM K = 3` отклонён из-за доли кластера 4,2 %,
`K-Means K = 4` — из-за 4,1 %. `Agglomerative` считается на подвыборке 5 000
и не используется для `predict()`.

Артефакты: `reports/clustering/` (`k_selection.csv`, `stability.csv`,
`cluster_profiles.csv`, `run_metadata.json`, графики и отчёт) и
`models/clustering_pipeline.joblib` (каталог `models/` не коммитится).

Ограничения: внешних меток нет, accuracy не используется; кластер 1 (70 %)
близок к среднему — это смешанный паттерн, а не резко выраженная группа;
названия паттернов требуют экспертной валидации.

## Отличия от block07_exam_project

- Нутриенты не суммируются на уровне приёма: используются средние значения и
  плотность на 100 ккал.
- Продукты без нутриентов не удаляются молча; сохраняются флаг `is_matched` и
  показатели полноты.
- Вместо эвристического выбора «короткого названия» используется курируемая
  таблица `src/resources/product_fdc_map.csv`; сомнительные названия остаются
  без матча.
- Поддержаны альтернативные `nutrient_id` USDA: energy `1008/2047/2048`,
  sugars `2000/1063`, fat `1004/1085`, carbs `1005/1050`, fiber `1079/2033`.
- Кэш продуктовой таблицы восстанавливает типы данных (`date`, `fdc_id`,
  `is_matched`, `reviewed`).
- Добавлены профилирование датасетов, CLI и pytest-тесты на синтетических
  данных.

## Правила подготовки

- Нутриенты USDA приведены на 100 г; масса порции в данных отсутствует.
- Средний профиль приёма — это состав «среднего продукта» при допущении равной
  массы продуктов. Допущение фиксируется в названиях колонок
  (`*_mean_per_100g`).
- Плотность на 100 ккал рассчитывается как `100 * nutrient_mean / energy_mean`.
- Пропуски не заменяются нулём. Явный `amount = 0` в USDA сохраняется как
  ноль; отсутствующая строка остаётся `NaN`.
- Для каждого приёма и дня возвращаются `n_products_with_nutrients`,
  `nutrient_completeness`, `core_completeness`, `core_complete` и
  `is_reliable`, а для каждого нутриента — `<nutrient>_n_products`,
  `<nutrient>_coverage` и `<nutrient>_missing`.
- `is_reliable` требует полного покрытия ядра (energy + БЖУ) всеми продуктами
  приёма/дня; «хоть один продукт с нутриентами» больше не считается надёжным.
- Сопоставление с USDA идёт только по курируемой таблице. Автоматический
  поиск (`search_products`) оставлен для обратной совместимости и синтетических
  тестов; в продакшн-пайплайне он не используется.
- Продукты без матча сохраняются с `is_matched = False` и пропущенными
  нутриентами; `match_source = "unmapped"`, `reviewed` показывает статус.

## Зависимости

Основные: `numpy`, `pandas`, `pyarrow`, `scikit-learn`, `matplotlib`, `joblib`.
Для разработки: `pytest`, `ruff`. Полный список — в `pyproject.toml`,
`requirements.txt` и `requirements-dev.txt`.
