# Экспертная валидация

Статус: не проведена.

Эксперту передаётся `label_template.csv`: без кластера, расстояния и confidence band.
Ключ `sample_key.csv` не передаётся эксперту.

Категории:
- высокоэнергетический белково-жировой;
- смешанный/типичный;
- растительный высококлетчаточный;
- другой;
- не относится.

После заполнения запустить:
`uv run python -m src.expert_validation --evaluate --key reports/expert_validation/sample_key.csv --labels reports/expert_validation/label_template.csv`
