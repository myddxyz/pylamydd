@echo off
title PylaMydd
echo [1/4] Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul

echo [2/4] Installing setuptools...
pip install setuptools --quiet 2>nul

echo [3/4] Installing dependencies...
pip install -r requirements.txt --quiet
pip install "adbutils>=2.0.0" --quiet
pip install "scrcpy-client@git+https://github.com/leng-yue/py-scrcpy-client.git@v0.5.0" --quiet --no-deps

echo [4/4] Starting PylaMydd...
echo.
:: Set paths so python can find the code in src/ and adbutils can find adb.exe in tools/
set PYTHONPATH=%~dp0src;%PYTHONPATH%
set PATH=%~dp0tools;%PATH%
python src\main.py

pause
