@echo off
REM Frontend startup script for Windows

echo ========================================
echo Starting Portfolio Optimizer Frontend
echo ========================================

cd /d %~dp0\portfolio_web\frontend

echo Installing/updating dependencies...
call npm install --silent

echo Starting React development server on http://localhost:3000
call npm start

pause
