@echo off
echo Starting LearnHub Pro...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Install requirements
echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo Failed to install dependencies
    echo Try: pip install Flask Werkzeug
)

REM Set environment variables for Flask
set FLASK_APP=app.py
set FLASK_DEBUG=1

REM Run the application
echo Starting server...
echo.
echo ========================================
echo    LearnHub Pro is starting...
echo    Open: http://localhost:5000
echo    Admin: admin / admin123
echo ========================================
echo.
python app.py