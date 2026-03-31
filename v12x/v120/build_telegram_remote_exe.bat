@echo off
setlocal
cd /d %~dp0
pyinstaller --noconfirm --onefile --name telegram_remote --distpath . --workpath build --specpath . run_telegram_worker.py
if exist build rmdir /s /q build
if exist telegram_remote.spec del /q telegram_remote.spec
echo.
echo Build complete. telegram_remote.exe created in project root.
endlocal
