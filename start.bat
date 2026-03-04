@echo off
title PylaMydd Launcher
echo Starting PylaMydd...
echo.

if exist "dist\PylaMyddRelease\Start_PylaMydd.bat" (
    cd dist\PylaMyddRelease
    call Start_PylaMydd.bat
    echo.
    echo PylaMydd has exited.
) else (
    echo [ERROR] The executable was not found. 
    echo Please run build.bat first to generate the release folder!
)
echo.
pause
