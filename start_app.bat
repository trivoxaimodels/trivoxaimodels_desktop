@echo off
REM VoxelCraft Desktop Application - Start Script
REM ================================================
REM Runs the application with virtual environment support

echo ============================================
echo VoxelCraft Desktop Application
echo ============================================
echo.

REM Configuration
set "VENV_DIR=venv"
set "MAIN_SCRIPT=main.py"

REM Check if Python is available
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://python.org
    pause
    exit /b 1
)
python --version
echo.

REM Check if virtual environment exists
echo [2/3] Checking virtual environment...
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Activating virtual environment...
    call %VENV_DIR%\Scripts\activate.bat
    if errorlevel 1 (
        echo WARNING: Failed to activate virtual environment, using system Python
    ) else (
        echo Virtual environment activated.
    )
) else (
    echo Virtual environment not found, using system Python
    echo.
    echo NOTE: To create a virtual environment, run:
    echo   python -m venv %VENV_DIR%
    echo   %VENV_DIR%\Scripts\activate.bat
    echo   pip install -r requirements.txt
    echo.
)
echo.

REM Check if .env file exists
if not exist ".env" (
    if exist ".env.example" (
        echo WARNING: .env file not found!
        echo Creating .env from .env.example...
        copy .env.example .env >nul
        echo IMPORTANT: Please edit .env with your Supabase credentials before continuing!
        echo.
        pause
    ) else (
        echo WARNING: Neither .env nor .env.example found!
        echo The application may not work correctly without environment variables.
        echo.
    )
)

REM Run the application
echo [3/3] Starting VoxelCraft...
echo ============================================
echo.

python %MAIN_SCRIPT%

REM Capture exit code
set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE% neq 0 (
    echo.
    echo ============================================
    echo Application exited with error code: %EXIT_CODE%
    echo ============================================
    pause
)

exit /b %EXIT_CODE%
