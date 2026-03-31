OKX Turtle Bot v102

Запуск: python main_v102.py

Главные изменения:
- исправлен persistent pipeline для GOOD review tags/comments;
- ускорено обновление таблицы открытых позиций после открытия и добора;
- счётчик ошибок теперь игнорирует сетевой шум WinError 10035 и временные scanner retry;
- Telegram worker по-прежнему поддерживается отдельным exe рядом с программой.
