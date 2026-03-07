@echo off
title PylaMydd
echo ============================================
echo    PylaMydd - Python Launcher
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/5] Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul

echo [2/5] Installing setuptools...
python -m pip install setuptools --quiet 2>nul

echo [3/5] Installing dependencies...
python -m pip install -r requirements.txt --quiet
python -m pip install "adbutils>=2.0.0" --quiet

echo [4/5] Installing scrcpy-client...
:: Check if git is available (needed for scrcpy-client install from GitHub)
git --version >nul 2>&1
if errorlevel 1 (
    echo    Git not found - installing scrcpy-client via pip fallback...
    python -m pip install scrcpy-client --quiet 2>nul
    if errorlevel 1 (
        echo    [WARNING] Could not install scrcpy-client automatically.
        echo    Please install Git from https://git-scm.com/downloads
        echo    Then re-run this script.
        pause
        exit /b 1
    )
) else (
    python -m pip install "scrcpy-client@git+https://github.com/leng-yue/py-scrcpy-client.git@v0.5.0" --quiet --no-deps
)

echo [5/5] Starting PylaMydd...
echo.
:: Set paths so python can find the code in src/ and adbutils can find adb.exe in tools/
set PYTHONPATH=%~dp0src;%PYTHONPATH%
set PATH=%~dp0tools;%PATH%
python src\main.py

echo.
if errorlevel 1 (
    echo ============================================
    echo    PylaMydd crashed! Check the error above.
    echo ============================================
)
pause
