@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/4] Detecting Python...
set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo Python launcher not found.
    echo Install Python or add it to PATH.
    exit /b 1
)

echo Using: %PY_CMD%
echo [2/4] Checking PyInstaller...
%PY_CMD% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed in this Python environment.
    echo Run: %PY_CMD% -m pip install pyinstaller
    exit /b 1
)

echo [3/4] Building telegram_worker.exe...
if not exist "%~dp0runtime" mkdir "%~dp0runtime"
if not exist "%~dp0runtime\pyinstaller_build" mkdir "%~dp0runtime\pyinstaller_build"
%PY_CMD% -m PyInstaller --noconfirm --clean --onefile --noconsole --name telegram_worker --distpath "%~dp0" --workpath "%~dp0runtime\pyinstaller_build\work" --specpath "%~dp0runtime\pyinstaller_build\spec" "%~dp0run_telegram_worker.py"
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo [4/4] Checking result...
if exist "%~dp0telegram_worker.exe" (
    echo OK: "%~dp0telegram_worker.exe"
    exit /b 0
)

echo telegram_worker.exe was not created.
exit /b 1
