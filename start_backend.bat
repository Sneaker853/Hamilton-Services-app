@echo off
REM Backend startup script for Windows

echo ========================================
echo Starting Portfolio Optimizer Backend
echo ========================================

cd /d %~dp0\portfolio_web\backend

echo Activating virtual environment...
call ..\..\.venv\Scripts\activate.bat

if "%BACKEND_INSTALL_DEPS%"=="1" (
	echo Installing/updating dependencies...
	pip install -q -r requirements.txt
) else (
	echo Skipping dependency install (set BACKEND_INSTALL_DEPS=1 to enable)
)

echo Starting FastAPI server on http://localhost:8000
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
