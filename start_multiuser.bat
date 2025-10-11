@echo off
echo Starting Insurance Portal Multi-User Application...

cd /d "C:\Users\SAMEER SHAH\Downloads\FinalWebsite-main\FinalWebsite-main"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Please run deploy_multiuser_windows.py first.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call "venv\Scripts\activate.bat"

REM Check if .env file exists
if not exist ".env" (
    echo [WARNING] .env file not found. Please create it with your configuration.
    echo You can use the .env template that was created during deployment.
    pause
)

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "static\renewals" mkdir static\renewals
if not exist "static\uploads" mkdir static\uploads
if not exist "temp" mkdir temp

REM Start application
echo.
echo ========================================
echo  Insurance Portal Multi-User Server
echo ========================================
echo.
echo Starting server...
echo Access the application at: http://localhost:5050
echo Press Ctrl+C to stop the server
echo.

REM Try to start with Waitress (Windows WSGI server)
python start_server.py

if errorlevel 1 (
    echo.
    echo Trying fallback startup method...
    python app_multiuser.py
)

echo.
echo Server stopped.
pause