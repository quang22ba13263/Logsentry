@echo off
REM Start LogSentry AI Flask Application
REM For Windows

echo =========================================
echo   LogSentry AI - Starting Server
echo =========================================
echo.

REM Check if virtual environment exists
if exist "venv" (
    echo [OK] Found virtual environment
    call venv\Scripts\activate.bat
) else (
    echo [!] Virtual environment not found
    echo     Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat

    echo     Installing dependencies...
    pip install -r requirements_flask.txt
)

REM Check if data directory exists
if not exist "data" (
    echo     Creating data directory...
    mkdir data\models data\processed data\raw
)

REM Start Flask application
echo.
echo [*] Starting Flask server on http://localhost:5000
echo.
echo     Default credentials:
echo     Username: admin
echo     Password: admin123
echo.
echo     Press Ctrl+C to stop
echo.
echo -----------------------------------------
echo.

python run.py

pause
