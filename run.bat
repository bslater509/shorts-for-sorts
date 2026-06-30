@echo off
:: Navigate to the script's directory
cd /d "%~dp0"

:: Check if Windows virtual environment exists
if not exist "venv\Scripts" (
    echo Error: Windows virtual environment 'venv\Scripts' not found.
    echo Please set up the project for Windows first by running:
    echo   python -m venv venv
    exit /b 1
)

:: Check if required packages are installed
venv\Scripts\python.exe -c "import questionary, kokoro_onnx, soundfile" >nul 2>&1
if errorlevel 1 (
    echo Installing missing dependencies...
    venv\Scripts\pip.exe install -r requirements.txt
)

:: Run the TUI
venv\Scripts\python.exe tui.py
