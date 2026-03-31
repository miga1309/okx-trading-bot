@echo off
setlocal
cd /d "%~dp0"

set PY_CMD=py -3
where py >nul 2>&1
if errorlevel 1 set PY_CMD=python

%PY_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name telegram_worker_gui --distpath "%~dp0" --workpath "%~dp0runtime\pyinstaller_build\work_gui" --specpath "%~dp0runtime\pyinstaller_build\spec_gui" "%~dp0telegram_worker_gui.py"
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

if exist "%~dp0telegram_worker_gui.exe" (
    echo OK: "%~dp0telegram_worker_gui.exe"
    exit /b 0
)

echo telegram_worker_gui.exe was not created.
exit /b 1
