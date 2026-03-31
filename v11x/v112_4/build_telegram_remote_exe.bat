@echo off
setlocal
cd /d %~dp0
pyinstaller --noconfirm --onefile --name telegram_remote run_telegram_worker.py
echo.
echo Build complete. Put dist\telegram_remote.exe anywhere and launch with:
echo telegram_remote.exe --project-root "%~dp0"
endlocal
