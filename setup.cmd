@echo off
REM Virtual Environment name
set "VENV_NAME=ma_venv"

REM Creating Virtual Environment
echo [INFO] Setting virtual environment
python -m venv ma_venv

REM Activating Virtual Environment
echo [INFO] Activating virtual environment
call "ma_venv\Scripts\activate.bat"

echo [INFO] Installing dependencies from requirements.txt
pip install -r requirements.txt

echo [INFO] Configuring and installing local web browser
set PLAYWRIGHT_BROWSERS_PATH=0
playwright install firefox

echo [INFO] Closing virtual environment
deactivate