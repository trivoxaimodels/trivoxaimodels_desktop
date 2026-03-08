@echo off
REM VoxelCraft Desktop Application - Simple Build Script
REM ===================================================
REM Builds the executable using PyInstaller with virtual environment

echo ============================================
echo  VoxelCraft Desktop Application Build
echo ============================================
echo.

REM Configuration
set "APP_NAME=VoxelCraft"
set "SPEC_FILE=VoxelCraft.spec"
set "BUILD_DIR=build"
set "DIST_DIR=dist"
set "VENV_DIR=venv"

REM Check if Python is available
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)
python --version
echo.

REM Create virtual environment if it doesn't exist
echo [2/5] Setting up virtual environment...
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    exit /b 1
)
echo Virtual environment activated.
echo.

REM Install/Update dependencies
echo [4/5] Installing dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

REM Ensure PyInstaller is installed
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller>=6.0
)
echo Dependencies installed.
echo.

REM Create .env from .env.example if it doesn't exist
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy .env.example .env >nul
        echo IMPORTANT: Edit .env with your Supabase credentials before running the app!
    )
)

REM Clean previous builds
if exist %BUILD_DIR% (
    echo Cleaning previous build...
    rmdir /s /q %BUILD_DIR% 2>nul
)
if exist %DIST_DIR% (
    echo Cleaning previous dist...
    rmdir /s /q %DIST_DIR% 2>nul
)
echo.

REM Build the executable
echo [5/5] Building executable...
echo This may take several minutes. Please wait...
echo.

python -m PyInstaller %SPEC_FILE% --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build Complete!
echo ============================================
echo.
echo Executable location: %DIST_DIR%\%APP_NAME%.exe
echo.
echo To run the application:
echo   1. Edit .env with your Supabase credentials
echo   2. Run %DIST_DIR%\%APP_NAME%.exe
echo.
echo To create a professional installer, run:
echo   build_complete.bat
echo.

pause
