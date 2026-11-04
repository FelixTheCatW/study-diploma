# Профиль данных



## diet_diary

- Строк: 5251
- Колонок: 7
- Память: 1.8 МБ
- Дубликатов строк: 0

### Колонки

| Колонка | Тип | Пропуски | Доля | Уникальных | Пример |
| --- | --- | --- | --- | --- | --- |
| ID | str | 0 | 0.0% | 611 | 721c929849fc713ce020c5a3e748f73f |
| date | str | 0 | 0.0% | 657 | 2020/11/17 |
| breakfast | str | 0 | 0.0% | 5250 | breakfast/293290_20201117_breakfast_1605569539_1.jpg;breakfast/293290_20201117_breakfast_1605569540_2.jpg\|\|\| |
| lunch | str | 0 | 0.0% | 5245 | lunch/293290_20201117_lunch_1605617876_1.jpg\|\|\|bun eggplant egg |
| supper | str | 0 | 0.0% | 5240 | supper/293290_20201117_supper_1605617925_1.jpg\|\|\|wine mustard meat |
| start_weight | float64 | 0 | 0.0% | 621 | 78.8 |
| weight | float64 | 0 | 0.0% | 612 | 78.4 |

### Числовые признаки

| column | count | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| start_weight | 5251 | 68.23 | 13.09 | 41.8 | 58 | 65.9 | 76.4 | 124 |
| weight | 5251 | 68.08 | 13.07 | 41.6 | 58 | 65.8 | 76.2 | 122.3 |

### Категориальные признаки

- `ID` — 413ef37ad8e3edf52fbbf1aa55dfe20c: 84, 3cf257fb218d22352ba783508c1acbb5: 79, f79ec07c022a94debf359aec111d8b0d: 67, cd7ac2370381d31ff6682341477782cd: 62, fb31bf0604ccc2dd899fccc2cebd7152: 57
- `date` — 2018/7/22: 70, 2018/7/23: 68, 2018/7/21: 67, 2018/7/20: 61, 2018/7/24: 60
- `breakfast` — |||: 2, breakfast/293290_20201117_breakfast_1605569539_1.jpg;breakfast/293290_20201117_breakfast_1605569540_2.jpg|||: 1, breakfast/293290_20201118_breakfast_1605667215_1.jpg|||dumpling: 1, breakfast/293290_20201119_breakfast_1605751810_1.jpg;breakfast/293290_20201119_breakfast_1605751811_2.jpg|||: 1, breakfast/293290_20201120_breakfast_1605827326_1.jpg;breakfast/293290_20201120_breakfast_1605827327_2.jpg|||bread milk: 1
- `lunch` — |||: 6, |||rice: 2, lunch/293290_20201117_lunch_1605617876_1.jpg|||bun eggplant egg: 1, lunch/293290_20201118_lunch_1605699259_1.jpg|||chicken noodle: 1, lunch/293290_20201119_lunch_1605792865_1.jpg|||rice: 1
- `supper` — |||: 11, |||meal_replacement_powder fruit: 2, supper/293290_20201117_supper_1605617925_1.jpg|||wine mustard meat: 1, supper/293290_20201118_supper_1605699286_1.jpg|||fish cucumber wine: 1, supper/293290_20201119_supper_1605792895_1.jpg|||: 1

### Предупреждения

- Высокая кардинальность: breakfast, lunch, supper

## health_fitness

- Строк: 200000
- Колонок: 23
- Память: 40.9 МБ
- Дубликатов строк: 0

### Колонки

| Колонка | Тип | Пропуски | Доля | Уникальных | Пример |
| --- | --- | --- | --- | --- | --- |
| participant_id | int64 | 0 | 0.0% | 871 | 1 |
| date | str | 0 | 0.0% | 360 | 2024/1/1 |
| age | int64 | 0 | 0.0% | 47 | 56 |
| gender | str | 0 | 0.0% | 3 | F |
| height_cm | float64 | 0 | 0.0% | 330 | 165.3 |
| weight_kg | float64 | 0 | 0.0% | 4580 | 50.55 |
| bmi | float64 | 0 | 0.0% | 641 | 18.5 |
| activity_type | str | 0 | 0.0% | 10 | Dancing |
| duration_minutes | float64 | 0 | 0.0% | 1320 | 42.1 |
| intensity | str | 0 | 0.0% | 3 | Low |
| calories_burned | float64 | 0 | 0.0% | 708 | 3.3 |
| daily_steps | int64 | 0 | 0.0% | 11533 | 7128 |
| avg_heart_rate | int64 | 0 | 0.0% | 121 | 103 |
| resting_heart_rate | float64 | 0 | 0.0% | 218 | 69.5 |
| blood_pressure_systolic | float64 | 0 | 0.0% | 354 | 110.7 |
| blood_pressure_diastolic | float64 | 0 | 0.0% | 310 | 72.9 |
| endurance_level | float64 | 0 | 0.0% | 1244 | 5.37 |
| sleep_hours | float64 | 0 | 0.0% | 61 | 6.6 |
| stress_level | int64 | 0 | 0.0% | 10 | 4 |
| hydration_level | float64 | 0 | 0.0% | 21 | 1.5 |
| smoking_status | str | 0 | 0.0% | 3 | Never |
| health_condition | str | 143434 | 71.7% | 3 | Diabetes |
| fitness_level | float64 | 0 | 0.0% | 2142 | 0.04 |

### Числовые признаки

| column | count | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| participant_id | 2e+05 | 436.2 | 251.2 | 1 | 219 | 436 | 654 | 871 |
| age | 2e+05 | 41.79 | 13.24 | 18 | 31 | 43 | 53 | 64 |
| height_cm | 2e+05 | 168.6 | 9.111 | 146.4 | 161.5 | 168.4 | 175.4 | 194.3 |
| weight_kg | 2e+05 | 61.37 | 8.447 | 41.13 | 55.1 | 60.85 | 67.07 | 93.81 |
| bmi | 2e+05 | 21.54 | 1.922 | 18.5 | 19.94 | 21.46 | 23.13 | 24.9 |
| duration_minutes | 2e+05 | 74.12 | 35.12 | 20 | 46.4 | 72.9 | 99.7 | 152 |
| calories_burned | 2e+05 | 15.34 | 9.958 | 0.8 | 7.8 | 13 | 20.6 | 87.8 |
| daily_steps | 2e+05 | 8627 | 2054 | 36 | 7202 | 8606 | 1.003e+04 | 1.686e+04 |
| avg_heart_rate | 2e+05 | 131.3 | 17.67 | 82 | 118 | 130 | 143 | 206 |
| resting_heart_rate | 2e+05 | 70.04 | 5.045 | 52.2 | 66.8 | 70.1 | 73.4 | 87.1 |
| blood_pressure_systolic | 2e+05 | 120.3 | 9.928 | 78 | 113.8 | 120.8 | 127.1 | 152.7 |
| blood_pressure_diastolic | 2e+05 | 80.39 | 8.012 | 58.7 | 74.8 | 80.6 | 85.8 | 107.3 |
| endurance_level | 2e+05 | 9.469 | 2.224 | 4.53 | 7.81 | 9.44 | 11.02 | 17.17 |
| sleep_hours | 2e+05 | 7.048 | 0.9733 | 4 | 6.4 | 7 | 7.7 | 10 |
| stress_level | 2e+05 | 5.47 | 1.917 | 1 | 4 | 5 | 7 | 10 |
| hydration_level | 2e+05 | 2.5 | 0.5788 | 1.5 | 2 | 2.5 | 3 | 3.5 |
| fitness_level | 2e+05 | 9.544 | 5.514 | 0.02 | 4.78 | 9.53 | 14.26 | 21.8 |

### Категориальные признаки

- `date` — 2024/4/6: 691, 2024/3/30: 688, 2024/3/27: 686, 2024/4/4: 686, 2024/3/25: 685
- `gender` — F: 99175, M: 97589, Other: 3236
- `activity_type` — Yoga: 20340, HIIT: 20225, Weight Training: 20204, Dancing: 20180, Swimming: 20170
- `intensity` — Medium: 100087, Low: 60283, High: 39630
- `smoking_status` — Never: 118063, Former: 47918, Current: 34019
- `health_condition` — nan: 143434, Hypertension: 30108, Diabetes: 18491, Asthma: 7967

## daily_nutrition

- Строк: 200000
- Колонок: 14
- Память: 23.3 МБ
- Дубликатов строк: 0

### Колонки

| Колонка | Тип | Пропуски | Доля | Уникальных | Пример |
| --- | --- | --- | --- | --- | --- |
| user_id | int64 | 0 | 0.0% | 3363 | 1 |
| diary_date | str | 0 | 0.0% | 200 | 2014-09-14 |
| calories | float64 | 0 | 0.0% | 4424 | 2924 |
| carbs | float64 | 0 | 0.0% | 739 | 340 |
| fat | float64 | 0 | 0.0% | 384 | 114 |
| protein | float64 | 0 | 0.0% | 413 | 186 |
| sodium | float64 | 0 | 0.0% | 6770 | 3658 |
| sugar | float64 | 0 | 0.0% | 383 | 109 |
| goal_calories | float64 | 0 | 0.0% | 3614 | 3173 |
| goal_carbs | float64 | 0 | 0.0% | 694 | 396 |
| goal_fat | float64 | 0 | 0.0% | 327 | 105 |
| goal_protein | float64 | 0 | 0.0% | 535 | 160 |
| goal_sodium | float64 | 0 | 0.0% | 38 | 2300 |
| goal_sugar | float64 | 0 | 0.0% | 270 | 119 |

### Числовые признаки

| column | count | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| user_id | 2e+05 | 1706 | 979.9 | 1 | 858 | 1726 | 2568 | 3363 |
| calories | 2e+05 | 1423 | 1104 | 0 | 1040 | 1409 | 1773 | 3.87e+05 |
| carbs | 2e+05 | 141.6 | 95.26 | 0 | 79 | 139 | 192 | 1.153e+04 |
| fat | 2e+05 | 52.35 | 41 | 0 | 29 | 49 | 70 | 9000 |
| protein | 2e+05 | 73.45 | 53.42 | 0 | 42 | 68 | 98 | 9000 |
| sodium | 2e+05 | 1297 | 1853 | 0 | 0 | 1000 | 2170 | 3.533e+05 |
| sugar | 2e+05 | 31.55 | 39.74 | 0 | 0 | 18 | 53 | 2688 |
| goal_calories | 2e+05 | 1806 | 532.7 | 0 | 1450 | 1706 | 2041 | 2.607e+04 |
| goal_carbs | 2e+05 | 189.3 | 85.5 | 0 | 150 | 188 | 234 | 3255 |
| goal_fat | 2e+05 | 61.26 | 28.42 | 0 | 46 | 57 | 71 | 869 |
| goal_protein | 2e+05 | 113.8 | 54.62 | 0 | 76 | 102 | 139 | 1311 |
| goal_sodium | 2e+05 | 1555 | 1131 | 0 | 0 | 2300 | 2300 | 2.301e+04 |
| goal_sugar | 2e+05 | 40.29 | 37.83 | 0 | 0 | 46 | 66 | 5085 |

### Категориальные признаки

- `diary_date` — 2015-01-20: 1546, 2015-01-05: 1540, 2015-01-12: 1527, 2015-01-21: 1524, 2015-01-13: 1518

## food_data

- Строк: 2679
- Колонок: 9
- Память: 0.8 МБ
- Дубликатов строк: 0

### Колонки

| Колонка | Тип | Пропуски | Доля | Уникальных | Пример |
| --- | --- | --- | --- | --- | --- |
| product_name | str | 85 | 3.2% | 2466 | Jben |
| category | str | 6 | 0.2% | 2295 | en:Dairies, en:Fermented foods, en:Fermented milk products, en:Spreads, en:Cheeses, en:Salted spreads, en:Cheese spreads, en:Fromage frais nature à 21%de matière grasse |
| energy_kcal_100g | float64 | 0 | 0.0% | 726 | 235 |
| fat_100g | float64 | 0 | 0.0% | 459 | 21 |
| sugars_100g | float64 | 1 | 0.0% | 463 | 0 |
| carbohydrates_100g | float64 | 0 | 0.0% | 591 | 3.5 |
| serving_size_g | float64 | 30 | 1.1% | 251 | 160 |
| packaging_quantity | float64 | 2638 | 98.5% | 15 | 1920 |
| source_url | str | 0 | 0.0% | 2679 | https://world.openfoodfacts.org/product/6111242106949 |

### Числовые признаки

| column | count | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| energy_kcal_100g | 2679 | 325.1 | 198 | 0 | 149 | 356 | 461 | 3070 |
| fat_100g | 2679 | 16.28 | 18.91 | 0 | 2.5 | 10 | 24 | 255 |
| sugars_100g | 2678 | 12.78 | 17.32 | 0 | 1.4 | 4.4 | 18 | 113 |
| carbohydrates_100g | 2679 | 34.61 | 28.36 | 0 | 6.498 | 32 | 60 | 340 |
| serving_size_g | 2649 | 79.59 | 99.53 | 0 | 23 | 42 | 100 | 1500 |
| packaging_quantity | 41 | 56.27 | 298.7 | 1 | 1 | 2 | 15 | 1920 |

### Категориальные признаки

- `product_name` — nan: 85, Nutella: 11, Original: 6, Camembert: 5, Real Mayonnaise: 4
- `category` — snacks, salty-snacks, appetizers, da:crackers: 11, Breakfasts,Spreads,Sweet spreads,fr:Pâtes à tartiner,Hazelnut spreads,Chocolate spreads,Cocoa and hazelnuts spreads: 10, Snacks, Salty snacks, Appetizers, Chips and fries, Crisps, Corn chips: 10, Snacks,Snacks sucrés,Cacao et dérivés,Chocolats,Chocolats noirs: 8, Snacks,Snacks sucrés,Biscuits et gâteaux,Biscuits: 7
- `source_url` — https://world.openfoodfacts.org/product/6111242106949: 1, https://world.openfoodfacts.org/product/50184453: 1, https://world.openfoodfacts.org/product/6111242100985: 1, https://world.openfoodfacts.org/product/7622210449283: 1, https://world.openfoodfacts.org/product/3017620425035: 1

### Предупреждения

- Высокая кардинальность: product_name, category, source_url