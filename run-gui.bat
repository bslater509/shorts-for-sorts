@echo off
cd /d "%~dp0"

echo Checking for virtual environment...
IF EXIST venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) ELSE IF EXIST .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

echo Starting the server...
python gui\server.py --https %*
pause
