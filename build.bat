@echo off
title PylaMydd - Build .exe
echo ============================================
echo    PylaMydd - Building Standalone .exe
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10, 3.11, or 3.12 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check Python Version (< 3.13 required)
python -c "import sys; exit(1 if sys.version_info >= (3, 13) else 0)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [CRITICAL ERROR] Python 3.13 or newer is currently completely incompatible with PylaMydd!
    echo Libraries such as 'scrcpy-client' and 'av' lack Windows binaries for versions ^>= 3.13.
    echo Please completely uninstall your current Python, and install Python 3.11 or 3.12 instead.
    echo Download here: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/9] Creating Virtual Environment...
if exist "build_env" rmdir /s /q build_env
python -m venv build_env
call build_env\Scripts\activate.bat

echo [2/9] Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul

echo [3/9] Installing setuptools...
python -m pip install setuptools --quiet 2>nul

echo [4/9] Installing PyInstaller...
python -m pip install pyinstaller --quiet

echo [5/9] Installing dependencies...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.txt! See the console above for reasons.
    pause
    exit /b 1
)
python -m pip install "adbutils>=2.0.0" --quiet

echo [6/9] Installing scrcpy-client...
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
    if errorlevel 1 (
        echo [ERROR] Failed to compile and install scrcpy-client through git!
        pause
        exit /b 1
    )
)

echo [7/9] Cleaning previous builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "PylaMydd.spec" del /q PylaMydd.spec

echo [8/9] Building PylaMydd.exe ...
echo    (This may take several minutes)
echo.

:: Build the EXE into a 'bin' distribution folder so the root stays clean
python -m PyInstaller --noconfirm --onedir --console --name PylaMydd --distpath dist\bin ^
    --paths "src" ^
    --add-data "cfg;cfg" ^
    --add-data "models;models" ^
    --add-data "state_finder/images_to_detect;state_finder/images_to_detect" ^
    --add-data "api/assets;api/assets" ^
    --add-data "tools/adb.exe;." ^
    --add-data "tools/AdbWinApi.dll;." ^
    --add-data "tools/AdbWinUsbApi.dll;." ^
    --add-data "latest_brawler_data.json;." ^
    --copy-metadata customtkinter ^
    --hidden-import scrcpy ^
    --hidden-import scrcpy.core ^
    --hidden-import adbutils ^
    --hidden-import easyocr ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import bettercam ^
    --hidden-import google_play_scraper ^
    --hidden-import discord ^
    --hidden-import shapely ^
    --hidden-import pyautogui ^
    --hidden-import pygetwindow ^
    --hidden-import win32gui ^
    --hidden-import win32con ^
    --hidden-import win32ui ^
    --hidden-import av ^
    --collect-all customtkinter ^
    --collect-all easyocr ^
    --collect-all onnxruntime ^
    --collect-all scrcpy ^
    --collect-all tkinter ^
    src\main.py

echo.
echo [9/9] Organizing output folder...
:: Create the clean user-facing root folder
mkdir "dist\PylaMyddRelease" >nul 2>&1

:: Move the user-editable folders from the bin folder to the clean root
move "dist\bin\PylaMydd\_internal\cfg" "dist\PylaMyddRelease\cfg" >nul 2>&1
move "dist\bin\PylaMydd\_internal\models" "dist\PylaMyddRelease\models" >nul 2>&1
move "dist\bin\PylaMydd\_internal\state_finder" "dist\PylaMyddRelease\state_finder" >nul 2>&1
move "dist\bin\PylaMydd\_internal\api" "dist\PylaMyddRelease\api" >nul 2>&1
move "dist\bin\PylaMydd\_internal\latest_brawler_data.json" "dist\PylaMyddRelease\" >nul 2>&1

:: Move the entire nasty bin folder into the clean root as 'system'
move "dist\bin\PylaMydd" "dist\PylaMyddRelease\system" >nul 2>&1

:: Clean up the temporary bin directory and virtual environment
rmdir /s /q "dist\bin" >nul 2>&1
call build_env\Scripts\deactivate.bat
rmdir /s /q "build_env" >nul 2>&1

:: Create the launcher script at the root
echo @echo off > "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo title PylaMydd >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo cd /d "%%~dp0" >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo system\PylaMydd.exe >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo if errorlevel 1 ( >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo     echo. >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo     echo ============================================ >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo     echo    PylaMydd crashed! Check the error above. >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo     echo ============================================ >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo     pause >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo ) >> "dist\PylaMyddRelease\Start_PylaMydd.bat"

if exist "dist\PylaMyddRelease\system\PylaMydd.exe" (
    echo ============================================
    echo    BUILD SUCCESSFUL!
    echo    Output: dist\PylaMyddRelease\
    echo ============================================
    echo.
    echo Distribute the entire "dist\PylaMyddRelease" folder.
) else (
    echo ============================================
    echo    BUILD FAILED - Check errors above
    echo ============================================
)
echo.
pause
