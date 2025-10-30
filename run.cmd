@echo off
REM Virtual Environment name
set "VENV_NAME=ma_venv"

REM Activating Virtual Environment
echo [INFO] Activating virtual environment
call "ma_venv\Scripts\activate.bat"

echo [INFO] Running proxy
set PLAYWRIGHT_BROWSERS_PATH=0
python proxy_ma.py

echo [INFO] Closing virtual environment
deactivate