@echo off
echo ========================================
echo  Insurance Portal - Optimized for 2-4 Users
echo  System: i3 2nd gen, 4GB RAM
echo ========================================
echo.

cd /d "C:\Users\SAMEER SHAH\Downloads\FinalWebsite-main\FinalWebsite-main"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo [INFO] Please run: python deploy_multiuser_windows.py
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call "venv\Scripts\activate.bat"

REM Check if .env file exists
if not exist ".env" (
    echo [WARNING] .env file not found.
    echo [INFO] Please create .env file with your configuration.
    pause
)

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "static\renewals" mkdir static\renewals
if not exist "static\uploads" mkdir static\uploads
if not exist "temp" mkdir temp

REM Set optimized environment variables
set PYTHONOPTIMIZE=1
set PYTHONUNBUFFERED=1
set USE_OPTIMIZED_CONFIG=1

echo [INFO] Starting optimized server for 2-4 concurrent users...
echo [INFO] Configuration: Resource-optimized for i3 2nd gen, 4GB RAM
echo.

REM Start optimized server
python start_server_optimized.py

if errorlevel 1 (
    echo.
    echo [INFO] Trying fallback startup method...
    python app_multiuser.py
)

echo.
echo [INFO] Server stopped.
pause
