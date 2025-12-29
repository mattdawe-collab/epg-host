@echo off
:: ========================================================
::   AI EPG BRIDGE - LAUNCHER
:: ========================================================
cd /d "%~dp0"

echo [1/3] Checking environment...
if not exist ".env" (
    echo [ERROR] .env file not found! 
    echo Please create the .env file with your API keys first.
    pause
    exit /b
)

:: Optional: Auto-install requirements if they haven't been installed yet
if not exist "logs\install_check.lock" (
    echo [2/3] First run detected. Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Check your Python installation.
        pause
        exit /b
    )
    if not exist "logs" mkdir logs
    echo installed > "logs\install_check.lock"
) else (
    echo [2/3] Dependencies already checked.
)

echo [3/3] Starting AI Bridge (Gemini 3.0 Flash)...
echo.
:: Run the Python script as a module from the root to ensure imports work
python src/main.py

echo.
echo ========================================================
echo   Process Complete.
echo ========================================================
pause