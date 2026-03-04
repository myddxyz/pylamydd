@echo off
title PylaMydd - Build .exe
echo ============================================
echo    PylaMydd - Building Standalone .exe
echo ============================================
echo.

echo [1/4] Installing PyInstaller...
python -m pip install pyinstaller --quiet

echo [2/4] Cleaning previous builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "PylaMydd.spec" del /q PylaMydd.spec

echo [3/4] Building PylaMydd.exe ...
echo    (This may take several minutes)
echo.

:: Build the EXE into a 'bin' distribution folder so the root stays clean
pyinstaller --noconfirm --onedir --console --name PylaMydd --distpath dist\bin ^
    --paths "src" ^
    --add-data "cfg;cfg" ^
    --add-data "models;models" ^
    --add-data "state_finder/images_to_detect;state_finder/images_to_detect" ^
    --add-data "api/assets;api/assets" ^
    --add-data "tools/adb.exe;." ^
    --add-data "tools/AdbWinApi.dll;." ^
    --add-data "tools/AdbWinUsbApi.dll;." ^
    --add-data "latest_brawler_data.json;." ^
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
    src\main.py

echo.
echo [4/4] Organizing output folder...
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

:: Clean up the temporary bin directory
rmdir /s /q "dist\bin" >nul 2>&1

:: Create the launcher script at the root
echo @echo off > "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo title PylaMydd >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo cd /d "%%~dp0" >> "dist\PylaMyddRelease\Start_PylaMydd.bat"
echo system\PylaMydd\PylaMydd.exe >> "dist\PylaMyddRelease\Start_PylaMydd.bat"

if exist "dist\PylaMyddRelease\system\PylaMydd\PylaMydd.exe" (
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
