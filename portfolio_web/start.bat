@echo off
REM Portfolio Web App Startup Script
REM Starts both backend and frontend in separate terminal windows

echo.
echo ============================================================
echo   PORTFOLIO OPTIMIZER - WEB APPLICATION STARTUP
echo ============================================================
echo.

REM Check if running from correct directory
if not exist "backend\main.py" (
    echo ERROR: Run this script from the portfolio_web directory
    echo Current directory: %cd%
    pause
    exit /b 1
)

REM Check if Node.js is installed
where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Download from: https://nodejs.org/
    pause
    exit /b 1
)

REM Check if Python is installed
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if PostgreSQL is running
REM (This is a simple check - can be enhanced)

echo Starting Portfolio Optimizer...
echo.

REM Start Backend
echo [1/2] Starting FastAPI Backend (port 8000)...
start "Portfolio Backend" cmd /k "cd backend && .\.venv\Scripts\python.exe main.py"

REM Wait a bit for backend to start
timeout /t 3 /nobreak

REM Start Frontend
echo [2/2] Starting React Frontend (port 3000)...
cd frontend
start "Portfolio Frontend" cmd /k "npm start"
cd ..

echo.
echo ============================================================
echo   STARTUP COMPLETE
echo ============================================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Press any key in the terminal windows to stop the services.
echo.
pause
