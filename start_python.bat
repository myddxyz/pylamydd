@echo off
set PYTHONPATH=%~dp0src;%PYTHONPATH%
set PATH=%~dp0tools;%PATH%
python -m src.main %*
