# Virtual Environment name
$VENV_NAME = "ma_venv"

# Creating Virtual Environment
Write-Host "[INFO] Setting virtual environment"
python -m venv $VENV_NAME

# Activating Virtual Environment
Write-Host "[INFO] Activating virtual environment"
$activateScript = ".\" + $VENV_NAME + "\Scripts\Activate.ps1"
. $activateScript

Write-Host "[INFO] Installing dependencies from requirements.txt"
pip install -r requirements.txt

Write-Host "[INFO] Configuring and installing local web browser"
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
playwright install firefox

Write-Host "[INFO] Closing virtual environment"
deactivate