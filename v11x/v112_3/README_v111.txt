OKX Turtle Bot v111

Запуск:
- python main_v111.py
- или python main.py

Важно:
- .env должен лежать в корне программы.
- telegram_worker.exe должен лежать в корне программы рядом с main_v111.py / main.py.

Что изменено в v111:
- bootstrap-stop ставится тем же запросом, что и открытие позиции
- жизненный цикл стопа: BOOTSTRAP -> ATR -> TURTLE
- мягкая верификация/health-check стопа без раннего panic-close
- ручной добор юнита после 4 через кнопку и окно подтверждения
- зачистка старых wrapper-файлов после архитектурного перехода


Hotfix v111_1:
- Fixed entry order rejection caused by custom attached stop algo client id.
- Run with python main_v111_1.py or python main.py.
