@echo off
REM VoxelCraft - Run Built Executable
REM ===================================
REM Runs the compiled executable from dist folder

echo ============================================
echo VoxelCraft - Running Executable
echo ============================================
echo.

set "APP_NAME=VoxelCraft"
set "EXE_PATH=dist\%APP_NAME%.exe"

REM Check if executable exists
if not exist "%EXE_PATH%" (
    echo ERROR: Executable not found at %EXE_PATH%
    echo.
    echo Please build the application first by running:
    echo   build.bat
    echo.
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    if exist ".env.example" (
        echo WARNING: .env file not found!
        echo Creating .env from .env.example...
        copy .env.example .env >nul
        echo IMPORTANT: Please edit .env with your Supabase credentials!
        echo.
        pause
    )
)

REM Run the executable
echo Starting %APP_NAME%...
echo.

"%EXE_PATH%"

set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE% neq 0 (
    echo.
    echo Application exited with error code: %EXIT_CODE%
    pause
)

exit /b %EXIT_CODE%
