@echo off
title ULTRON - Local AI Assistant
echo.
echo  ============================================================
echo   ULTRON - Local AI Assistant
echo  ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found in PATH.
    echo  Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Change to project directory
cd /d "%~dp0"

REM Check if dependencies are installed
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo  Dependencies not installed. Installing now...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo  ERROR: Failed to install dependencies.
        echo  Try: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo  Dependencies installed successfully.
    echo.
)

REM Check if Ollama is running
echo  Checking Ollama service...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo  WARNING: Ollama not detected on port 11434.
    echo  Starting in offline mode. To enable AI:
    echo    1. Install Ollama from https://ollama.ai
    echo    2. Run: ollama pull gpt-oss:20b
    echo    3. Start Ollama, then relaunch ULTRON
    echo.
)

REM Launch ULTRON
echo  Starting ULTRON...
echo.
python main.py %*

if errorlevel 1 (
    echo.
    echo  ULTRON exited with an error.
    echo  Check logs\ultron.log for details.
    pause
)
