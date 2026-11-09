# Сопоставление DietDiary с USDA и обработка пропусков

Дата: 2026-11-10. Ветка: `feature/matching-fix`.

## 1. Проблема

В USDA FoodData Central отсутствие строки в `food_nutrient.csv` не означает
ноль. Это может быть неизмеренный или невнесённый нутриент. Замена таких
пропусков нулём искажает профиль продукта и создаёт кластеры по наличию
записи в USDA, а не по питанию.

Примеры:

| Продукт | Было | Корректная запись USDA | Проверка |
|---|---|---|---|
| tomato | `1750354` Foundation, sugars отсутствует | `170457` SR Legacy | sugars 2,63 г; sat fat 0,028 г; sodium 5 мг |
| corn | `748323` `Oil, corn`, нет protein/carbs/water | `169998` SR Legacy | protein 3,27 г; carbs 18,7 г; sugars 6,26 г |
| chicken | `173564` `Fat, chicken` | `171447` SR Legacy | sugars 0,0; fiber 0,0 — явные нули |
| egg | `172673` `Bread, egg` | `171287` SR Legacy | energy 143 ккал; protein 12,56 г |

Правило: `amount == 0` — настоящий ноль; отсутствующая строка — `NaN`.

## 2. Что изменено

- Поддержаны альтернативные `nutrient_id`:
  - energy: `1008`, затем `2047`, затем `2048`;
  - sugars: `2000`, затем `1063`;
  - fat: `1004`, затем `1085`;
  - carbohydrates: `1005`, затем `1050`;
  - fiber: `1079`, затем `2033`.
- Явные нули сохраняются; отсутствующие значения не заполняются нулём.
- Эвристический матчинг по короткому названию заменён курируемой таблицей
  `src/resources/product_fdc_map.csv` (197 продуктов).
- Для каждого приёма и дня добавлены `n_products`, `<nutrient>_n_products`,
  `<nutrient>_coverage`, `<nutrient>_missing`, `core_completeness`,
  `core_complete`, `is_reliable`. Среднее по нутриенту считается только при
  достаточном числе известных продуктов (`min_products_with_nutrients`).
- `is_reliable` требует полного покрытия ядра (energy + БЖУ), а не «хотя бы
  одного продукта с нутриентами».

## 3. Покрытие

- Всего строк продуктов: 52 479.
- Сопоставлено: 47 118 (89,8 %).
- Уникальных продуктов: 197; сопоставлено 165; намеренно оставлено без матча
  32.
- Приёмов: 15 323; полное покрытие ядра: 10 817 (70,6 %).
- Дней: 5 249.

Основные несопоставленные продукты: `vegetable` (1 277 строк), `soup` (916),
`meat` (871), `green` (773), `fruit` (268), `salad` (225), `shellfish` (170),
`sauce` (135). Эти названия неоднозначны: автоматический матч дал бы ложный
профиль. Они сохраняются с `is_matched = False`.

## 4. Пропуски

Покрытие на уровне продуктов после курирования:

| Нутриент | Доля строк с `NaN` |
|---|---:|
| energy_kcal | 10,2 % |
| protein_g | 10,2 % |
| fat_g | 10,2 % |
| carbohydrates_g | 10,2 % |
| fiber_g | 14,6 % |
| sugars_g | 20,5 % |
| saturated_fat_g | 14,0 % |
| cholesterol_mg | 12,5 % |
| sodium_mg | 10,2 % |
| potassium_mg | 10,2 % |
| water_g | 10,2 % |

Полное покрытие на уровне приёма (все продукты приёма имеют значение):

| Нутриент | Доля приёмов с полным покрытием |
|---|---:|
| energy_kcal, protein_g, fat_g, carbohydrates_g, sodium_mg, potassium_mg, water_g | 70,6 % |
| cholesterol_mg | 65,2 % |
| fiber_g | 60,9 % |
| saturated_fat_g | 62,0 % |
| sugars_g | 50,8 % |

Пропуски не удалены и не заменены нулём. Для кластеризации основной набор —
приёмы с `core_complete = True`; остальные используются в чувствительном
анализе с медианной импутацией и missing-индикаторами.

## 5. Контрольные проверки

- `tomato`: sugars 2,63, sat fat 0,028, sodium 5,0 — не ноль.
- `corn`: protein 3,27, carbohydrates 18,7, sugars 6,26 — не ноль.
- `chicken`: sugars 0,0, fiber 0,0 — явные нули сохранены.
- `water` (трактуется как water spinach): sugars отсутствует, остаётся `NaN`.
- `egg`: energy 143, protein 12,56, sugars 0,37.

## 6. Ограничения

- 32 продукта без матча: неоднозначные названия или отсутствие подходящей
  записи в USDA. Это осознанное решение, а не потеря данных.
- Часть сопоставлений — прокси: `fish` (mixed whitefish), `nut` (mixed nuts),
  `seeds` (sunflower kernels), `sushi` (California roll), `tacos` (soft taco),
  `cheese` (cheddar), `oil` (olive oil), `meal_replacement_powder`
  (nutritional shake powder). Они отмечены в `notes`.
- `rice` и `noodle` сопоставлены с вариантами «with salt»: в SR Legacy нет
  варианта без соли для этих описаний. Это влияет на sodium.
- Для продуктов без указания приготовления выбран generic-вариант USDA
  (raw/cooked); допущение фиксируется в `match_name`.
- Пропуски остаются `NaN`; медианная импутация должна выполняться внутри
  Pipeline и только на обучающей/reference-выборке.

## 7. Воспроизведение

```powershell
$env:DIPLOMA_USDA_DIR = "D:\study\ml\study-ml\data\FoodData_Central_csv_2026-04-30"
uv run python -m src.prepare --force
uv run pytest -q
```

Результат: `data/processed/product_table.csv`, `meal_table.csv`,
`day_table.csv`. Кэш `data/` в репозиторий не входит.
