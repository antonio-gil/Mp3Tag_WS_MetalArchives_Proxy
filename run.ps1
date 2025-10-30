# Virtual Environment name
$VENV_NAME = "ma_venv"

# Activating Virtual Environment
Write-Host "[INFO] Activating virtual environment"
$activateScript = ".\" + $VENV_NAME + "\Scripts\Activate.ps1"
. $activateScript

Write-Host "[INFO] Running proxy"
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
python proxy_ma.py

Write-Host "[INFO] Closing virtual environment"
deactivate