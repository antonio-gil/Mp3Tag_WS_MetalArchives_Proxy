# Virtual Environment name
$VENV_NAME = "ma_venv"

# Activating Virtual Environment
Write-Host "[INFO] Activating virtual environment"
$activateScript = ".\" + $VENV_NAME + "\Scripts\Activate.ps1"
. $activateScript

Write-Host "[INFO] Running proxy"
python proxy_ma.py

Write-Host "[INFO] Closing virtual environment"
deactivate