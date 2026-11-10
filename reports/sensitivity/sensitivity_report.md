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

## Выводы по текущему запуску

- `no_sodium`, `no_water`, `no_energy`: ARI `0,886`, `0,894`, `0,790`; решение не держится на одном нутриенте.
- `no_clip`: ARI `0,562`, минимальная доля кластера `0,1 %`; clip обязателен, иначе появляется вырожденный кластер.
- `ilr_only`: ARI `0,064`, минимальная доля `1,2 %`; только композиции БЖУ недостаточно, плотности нутриентов несут основной сигнал.
- `relaxed_all_meals`: ARI `0,661`, минимальная доля `1,3 %`; при добавлении неполных приёмов с импутацией K=3 вырождается. Основная выборка `core_complete` обоснована; вывод по всем приёмам не защищается.
- `no_meal_replacement`: ARI `0,441`, минимальная доля `19,1 %`, 9 875 приёмов. После удаления `meal_replacement_powder` K=3 остаётся невырожденным, но разбиение существенно меняется: высокоэнергетический кластер частично держится на этом продукте.
- `kmeans_k2`: ARI `0,583`; K=2 — другое, более грубое решение, а не замена K=3.
- `gmm_k3`: ARI `0,252`, минимальная доля `4,2 %`; GMM K=3 отклонён.
- `gmm_k2`: ARI `0,346`; мягкое отнесение даёт другое разбиение и не заменяет baseline.

Итог: `K-Means, K=3` на `core_complete` с clip остаётся основным решением, но кластер 0 нельзя обобщать как общий «высокоэнергетический» паттерн: 67 % его приёмов содержат `meal_replacement_powder`. Нужна экспертная проверка и отдельный анализ этого продукта.
