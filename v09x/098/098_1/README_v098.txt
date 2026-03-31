OKX Turtle Bot v098

Главный файл: main_v098.py
Telegram worker source: run_telegram_worker.py
Telegram worker exe: telegram_worker.exe
Очередь Telegram: runtime/telegram_queue
Лог worker: logs/telegram_worker.log
PID worker: runtime/telegram_worker.pid

Важно:
- TG START запускает только telegram_worker.exe.
- Если exe отсутствует, в GUI будет статус TG: EXE MISS.
- В VPN добавляйте именно telegram_worker.exe.

Как собрать telegram_worker.exe на Windows:
1. Положите папку v098 в обычную рабочую директорию.
2. Запустите build_telegram_worker_exe.bat.
3. После сборки рядом с main_v098.py появится telegram_worker.exe.
4. Добавьте telegram_worker.exe в VPN.
5. Запустите main_v098.py и нажмите TG START.
