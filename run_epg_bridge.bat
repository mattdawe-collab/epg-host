@echo off
:: ========================================================
::   AI EPG BRIDGE - LOCAL PC LAUNCHER
::   Requires VPN to be active for IPTV provider access
:: ========================================================
cd /d "%~dp0"

echo ========================================================
echo   AI EPG BRIDGE - LOCAL PC MODE
echo ========================================================
echo.

echo [1/5] Checking environment...
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please create the .env file with your API keys first.
    pause
    exit /b
)

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Run: python -m venv venv
    pause
    exit /b
)

echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/5] Starting AI Bridge (Gemini 3.0 Flash)...
echo.
python src/main.py

if %errorlevel% neq 0 (
    echo [ERROR] Main script failed!
    pause
    exit /b
)

echo.
echo [4/5] Deploying EPG (unzip to epg.xml)...
python src/deploy_epg.py

echo.
echo [5/5] Pushing to GitHub...
python src/push_to_github.py

echo.
echo ========================================================
echo   All done! EPG updated and pushed to GitHub.
echo ========================================================
pause
