# Sensitivity-анализ кластеризации

Reference: core_complete, K-Means, clip=True, K=3.

| variant | algorithm | k | n_features | n_samples_fit | n_common | ari_vs_reference | min_cluster_share | note |
|---|---|---|---|---|---|---|---|---|
| reference_kmeans | kmeans | 3 | 16 | 10817 | 10817 | 1.000 | 0.119 | core_complete, clip=True |
| kmeans_k2 | kmeans | 2 | 16 | 10817 | 10817 | 0.583 | 0.206 | same features |
| gmm_k2 | gmm | 2 | 16 | 10817 | 10817 | 0.346 | 0.142 | same features |
| gmm_k3 | gmm | 3 | 16 | 10817 | 10817 | 0.252 | 0.042 | same features |
| no_sodium | kmeans | 3 | 14 | 10817 | 10817 | 0.886 | 0.124 | feature ablation |
| no_water | kmeans | 3 | 14 | 10817 | 10817 | 0.894 | 0.114 | feature ablation |
| no_energy | kmeans | 3 | 15 | 10817 | 10817 | 0.790 | 0.137 | feature ablation |
| ilr_only | kmeans | 3 | 3 | 10817 | 10817 | 0.064 | 0.012 | composition + complexity only |
| no_clip | kmeans | 3 | 16 | 10817 | 10817 | 0.562 | 0.001 | no robust-z clipping |
| relaxed_all_meals | kmeans | 3 | 16 | 15323 | 10817 | 0.661 | 0.013 | all meals, median core imputation; imputed_core=139 |
| no_meal_replacement | kmeans | 3 | 16 | 9875 | 9875 | 0.441 | 0.191 | excluded 1158 meal_replacement_powder meals |

## Как читать

- `ari_vs_reference` — совпадение с основным решением на `core_complete`-выборке.
- `min_cluster_share` — минимальная доля кластера; ниже 5 % решение вырождается.
- `relaxed_all_meals` — чувствительность к отбору только полных приёмов; ядро импутировано медианой.
- `no_sodium`, `no_water`, `no_energy`, `ilr_only` — проверка, не держится ли решение на одном признаке.

## Решение

Решение принимается по совокупности ARI, размера кластеров и интерпретируемости. Если ablation резко снижает ARI, текущий K не защищается; если `relaxed_all_meals` даёт низкий ARI, присутствует selection bias по полноте профиля.

## Выводы

- `no_sodium`, `no_water`, `no_energy`: ARI остаётся высоким; решение не держится на одном нутриенте.
- `no_clip`: ARI `0.562`, min share `0.1%`; без clip решение вырождается.
- `ilr_only`: ARI `0.064`; только композиции БЖУ недостаточно, плотности нутриентов несут основной сигнал.
- `relaxed_all_meals`: ARI `0.661`, min share `1.3%`; неполные приёмы не подтверждают основное решение.
- `no_meal_replacement`: ARI `0.441`, min share `19.1%`; кластер 0 частично определяется `meal_replacement_powder`.
- `kmeans_k2`: ARI `0.583`; K=2 — другое, более грубое решение.
- `gmm_k3`: ARI `0.252`, min share `4.2%`; GMM K=3 отклонён.

Итог: основной вариант — `K-Means` на `core_complete` с clip. Кластер 0 нельзя обобщать как общий паттерн, если в нём доминирует `meal_replacement_powder`; это фиксируется в решении недели 4.
