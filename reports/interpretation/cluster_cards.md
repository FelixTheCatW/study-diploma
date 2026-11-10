# Карточки кластеров

## Кластер 0 — высокоэнергетический белково-жировой

- Размер: 1286 (11.9%).
- Приёмы: завтрак 18.4%, обед 10.7%, ужин 70.8%.
- Среднее число продуктов: 1.99; энергоплотность: 253.5 ккал/100 г.

Тип: продукт-специфичный; 67% приёмов содержат `meal_replacement_powder`.

Отличия от общего среднего:

| feature | cluster_mean | overall_mean | z_score |
|---|---|---|---|
| energy_density | 253.549 | 119.349 | 1.887 |
| ilr_protein_fat_carb | 1.248 | 0.251 | 1.163 |
| log_n_products | 1.044 | 1.360 | -0.924 |
| ilr_fat_carb | 0.638 | -0.606 | 0.857 |
| saturated_fat_g_density | 0.617 | 1.166 | -0.644 |

Доля приёмов с флагами:

| n | missing_input | high_saturated_fat | high_sugars | high_sodium | low_fiber | low_protein |
|---|---|---|---|---|---|---|
| 1286 | 0.033 | 0.132 | 0.020 | 0.733 | 0.796 | 0.123 |

Частые продукты:

| product | n_meals | share |
|---|---|---|
| meal_replacement_powder | 865 | 0.673 |
| egg | 161 | 0.125 |
| beef | 108 | 0.084 |
| cabbage | 106 | 0.082 |
| chicken | 93 | 0.072 |

Примеры ближайших к центроиду:

- `5f2f06666e5c2ada74431f799098ffa7|2018-06-09|supper` (supper): meal_replacement_powder, tofu; энергоплотность 268.0 ккал/100 г.
- `c288931d12736d98f2a6028c7f9fe126|2018-01-22|lunch` (lunch): egg, meal_replacement_powder; энергоплотность 267.5 ккал/100 г.
- `5bc7b3db8c7eda5938e402b5384eaa8f|2019-03-10|supper` (supper): meal_replacement_powder, omelette; энергоплотность 273.0 ккал/100 г.

## Кластер 1 — смешанный/типичный

- Размер: 7574 (70.0%).
- Приёмы: завтрак 47.2%, обед 30.1%, ужин 22.7%.
- Среднее число продуктов: 3.35; энергоплотность: 111.5 ккал/100 г.

Тип: смешанный/типичный.

Отличия от общего среднего:

| feature | cluster_mean | overall_mean | z_score |
|---|---|---|---|
| saturated_fat_g_density | 1.398 | 1.166 | 0.273 |
| potassium_mg_density | 195.646 | 251.660 | -0.264 |
| fiber_g_density | 1.112 | 1.580 | -0.235 |
| sugars_g_density | 2.538 | 3.313 | -0.206 |
| log_n_products | 1.425 | 1.360 | 0.190 |

Доля приёмов с флагами:

| n | missing_input | high_saturated_fat | high_sugars | high_sodium | low_fiber | low_protein |
|---|---|---|---|---|---|---|
| 7574 | 0.004 | 0.315 | 0.165 | 0.200 | 0.210 | 0.207 |

Частые продукты:

| product | n_meals | share |
|---|---|---|
| egg | 2973 | 0.393 |
| milk | 1804 | 0.238 |
| cabbage | 1118 | 0.148 |
| rice | 1111 | 0.147 |
| chicken | 1069 | 0.141 |

Примеры ближайших к центроиду:

- `fe7c14c87cfd528d8ee4c8ae7cbd7c0f|2018-07-29|breakfast` (breakfast): corn, egg, porridge; энергоплотность 100.0 ккал/100 г.
- `cb90a40b25698ffeb2604d8469777f6a|2018-07-17|lunch` (lunch): chicken, kelp, melon; энергоплотность 97.3 ккал/100 г.
- `8b750c0dbf493b5bcb1d02c318646fbb|2018-07-21|breakfast` (breakfast): bamboo_shoot, egg, noodle; энергоплотность 102.7 ккал/100 г.

## Кластер 2 — растительный высококлетчаточный

- Размер: 1957 (18.1%).
- Приёмы: завтрак 29.9%, обед 27.7%, ужин 42.4%.
- Среднее число продуктов: 3.00; энергоплотность: 61.5 ккал/100 г.

Тип: выраженный паттерн.

Отличия от общего среднего:

| feature | cluster_mean | overall_mean | z_score |
|---|---|---|---|
| fiber_g_density | 4.210 | 1.580 | 1.316 |
| sugars_g_density | 7.651 | 3.313 | 1.151 |
| potassium_mg_density | 493.076 | 251.660 | 1.139 |
| ilr_fat_carb | -1.808 | -0.606 | -0.828 |
| energy_density | 61.492 | 119.349 | -0.814 |

Доля приёмов с флагами:

| n | missing_input | high_saturated_fat | high_sugars | high_sodium | low_fiber | low_protein |
|---|---|---|---|---|---|---|
| 1957 | 0.014 | 0.072 | 0.719 | 0.126 | 0.014 | 0.500 |

Частые продукты:

| product | n_meals | share |
|---|---|---|
| cabbage | 441 | 0.225 |
| milk | 377 | 0.193 |
| potato | 351 | 0.179 |
| corn | 283 | 0.145 |
| shrimp | 268 | 0.137 |

Примеры ближайших к центроиду:

- `4fd6504b6b511fd87932502209e16f2b|2018-11-18|supper` (supper): corn, radish; энергоплотность 51.0 ккал/100 г.
- `6840c6d051e3347351c73d817838756d|2020-07-31|supper` (supper): celery, corn; энергоплотность 50.0 ккал/100 г.
- `1fa48a99b06e0babd604fcabcf563692|2018-09-06|breakfast` (breakfast): corn, porridge, water; энергоплотность 58.7 ккал/100 г.
