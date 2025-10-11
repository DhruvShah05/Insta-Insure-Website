@echo off
setlocal enabledelayedexpansion
echo ========================================
echo INSURANCE PORTAL - PRODUCTION DEPLOYMENT
echo Optimized for 5 Concurrent Users
echo ========================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [1/8] Creating virtual environment...
REM Create virtual environment if it doesn't exist
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo [2/8] Activating virtual environment...
REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo [3/8] Upgrading pip and installing production dependencies...
REM Upgrade pip and install production server
python -m pip install --upgrade pip
pip install waitress

echo [4/8] Installing application dependencies...
REM Install requirements
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    pause
    exit /b 1
)

echo [5/8] Validating environment configuration...
REM Check if .env file exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please create .env file with your configuration
    echo See .env.example for required variables
    pause
    exit /b 1
)

echo [6/8] Creating required directories...
REM Create required directories for production
for %%d in (logs temp uploads static\js) do (
    if not exist "%%d" (
        echo Creating directory: %%d
        mkdir "%%d"
    )
)

echo [7/8] Initializing production optimizations...
REM Set production environment variables
set FLASK_ENV=production
set PYTHONPATH=%CD%
set PRODUCTION_MODE=1

REM Run production integration validation
echo Validating production setup...
python production_integration.py
if errorlevel 1 (
    echo WARNING: Some production optimizations may not be available
)

REM Validate critical production files
if not exist "database.py" (
    echo WARNING: database.py not found - database optimizations disabled
)
if not exist "static\js\performance.js" (
    echo WARNING: performance.js not found - frontend optimizations disabled
)
if not exist "combined_app.py" (
    echo ERROR: combined_app.py not found - using fallback app.py
    set USE_FALLBACK=1
)

echo [8/8] Starting production server...
echo ========================================
echo PRODUCTION SERVER STARTING
echo ========================================
echo Server: Waitress WSGI Server (Production)
echo URL: http://localhost:5050
echo Concurrent Users: Optimized for 5+ users
echo Features: Database pooling, Request limiting, Frontend optimization
echo ========================================
echo Press Ctrl+C to stop the server
echo ========================================

REM Start with production optimizations
if "%USE_FALLBACK%"=="1" (
    echo WARNING: Using fallback mode - some optimizations may not be available
    waitress-serve --host=0.0.0.0 --port=5050 --threads=4 --connection-limit=1000 app:app
) else (
    echo Starting with full production optimizations...
    waitress-serve --host=0.0.0.0 --port=5050 --threads=8 --connection-limit=1000 --cleanup-interval=30 --channel-timeout=120 combined_app:app
)

if errorlevel 1 (
    echo ERROR: Failed to start production server
    echo Falling back to development server...
    echo WARNING: Development server is not optimized for concurrent users
    python combined_app.py
    if errorlevel 1 (
        python app.py
    )
)

pause
