# Дипломный проект: анализ пищевого поведения

Неделя 2: загрузка, анализ и подготовка данных.

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
  analyze.py           CLI анализа датасетов
  prepare.py           CLI подготовки DietDiary + USDA
  utils/
    diary.py           разбор DietDiary
    usda.py            поиск в USDA и обогащение нутриентами
tests/                 pytest-тесты на синтетических данных
data/                  исходные датасеты
data/processed/        результат подготовки
reports/               отчёт профилирования
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
611 пользователей и 197 уникальных продуктов; доля сопоставленных продуктов —
99,8 %. Пропуски нутриентов не удаляются: приёмы и дни с неполным профилем
помечаются через `is_reliable`.

## Отличия от block07_exam_project

- Нутриенты не суммируются на уровне приёма: используются средние значения и
  плотность на 100 ккал.
- Продукты без нутриентов не удаляются молча; сохраняются флаг `is_matched` и
  показатели полноты.
- Добавлен выбор лучшего матча USDA и матчинг по `short_description`
  брендированных продуктов.
- Кэш продуктовой таблицы восстанавливает типы данных (`date`, `fdc_id`,
  `is_matched`).
- Добавлены профилирование датасетов, CLI и pytest-тесты на синтетических
  данных.

## Правила подготовки

- Нутриенты USDA приведены на 100 г; масса порции в данных отсутствует.
- Средний профиль приёма — это состав «среднего продукта» при допущении равной
  массы продуктов. Допущение фиксируется в названиях колонок
  (`*_mean_per_100g`).
- Плотность на 100 ккал рассчитывается как `100 * nutrient_mean / energy_mean`.
- Пропуски не заменяются нулём. Для каждого приёма и дня возвращаются
  `n_products_with_nutrients`, `nutrient_completeness` и `is_reliable`.
- Сопоставление с USDA выбирает лучший матч: generic-описание →
  брендированный продукт → категория; внутри источника — точное совпадение,
  затем более короткое название.
- Продукты без матча сохраняются с `is_matched = False` и пропущенными
  нутриентами.

## Зависимости

Основные: `numpy`, `pandas`, `pyarrow`. Для тестов: `pytest`.
Полный список — в `pyproject.toml`, `requirements.txt` и
`requirements-dev.txt`.
