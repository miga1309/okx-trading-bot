\
@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed in this Python environment.
    echo Install it with: python -m pip install pyinstaller
    exit /b 1
)

echo [2/3] Building telegram_worker.exe...
if not exist "%~dp0runtime" mkdir "%~dp0runtime"
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --noconsole ^
  --name telegram_worker ^
  --distpath "%~dp0" ^
  --workpath "%~dp0runtime\pyinstaller_build\work" ^
  --specpath "%~dp0runtime\pyinstaller_build\spec" ^
  "%~dp0run_telegram_worker.py"
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo [3/3] Done. File created:
if exist "%~dp0telegram_worker.exe" (
    echo %~dp0telegram_worker.exe
    exit /b 0
) else (
    echo telegram_worker.exe was not created.
    exit /b 1
)
