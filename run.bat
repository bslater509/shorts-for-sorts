@echo off
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv" (
    echo Error: Virtual environment 'venv' not found.
    echo Please set up the project first or run 'python -m venv venv' and install requirements.
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install Python deps if needed
python -c "import fastapi, uvicorn, multipart, kokoro_onnx, soundfile" >nul 2>&1
if errorlevel 1 (
    echo Installing missing Python dependencies...
    pip install -r requirements.txt
)

REM Build frontend if npm available and gui\frontend exists
if exist "gui\frontend" (
    where npm >nul 2>&1
    if not errorlevel 1 (
        echo Building frontend...
        pushd gui\frontend
        if not exist "node_modules" (
            call npm install
        )
        call npm run build
        popd
    )
)

echo ==========================================================
echo  Starting Shorts Creator Web GUI Server...
echo  Access the interface locally at: http://localhost:5000
echo ==========================================================
echo.

python gui\server.py
