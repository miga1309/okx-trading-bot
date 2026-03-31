OKX Turtle Bot v084_1 — modular foundation patch

Что в патче:
- вынесены модули: trade_models, diagnostics_logging, market_data_cache, okx_gateway, popups, analysis_exporter
- основной файл: main_v084_1.py
- UI layout копия: ui_layout_v084_1.py
- popup открытой позиции: 60 свечей для Turtle 20, 80 свечей для Turtle 55
- popup открытой позиции: попытка поставить метки доборов юнитов из position_journal
- стартовый размер окна сделан компактнее

Как ставить:
1. Положить все файлы рядом с текущим проектом v084.
2. Не удалять оригинальные main_v084.py и ui_layout_v082_1.py.
3. Запускать main_v084_1.py.

Если в проекте используются относительные пути к ресурсам, лучше сначала сделать копию папки v084 и уже в ней заменить/добавить эти файлы.
