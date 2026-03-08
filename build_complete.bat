@echo off
chcp 65001 >nul
title Voxel Craft v1.0.0 - Complete Build System
cls

echo ============================================
echo  Voxel Craft v1.0.0 - Complete Build System
echo ============================================
echo.
echo This script will:
echo   [1] Build the executable using PyInstaller
echo   [2] Create the Windows installer using Inno Setup
echo   [3] Package everything for distribution
echo.
echo Features included in installer:
echo   - Professional Antigravity style setup wizard with logo
echo   - License agreement page
echo   - Custom installation path selection
echo   - Desktop shortcut option
echo   - Launch app after install option
echo   - Auto-upgrade support
echo.
pause
cls

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Not running as administrator.
    echo Some operations may fail. It is recommended to run as admin.
    echo.
    pause
    cls
)

REM Configuration
set "APP_NAME=VoxelCraft"
set "APP_VERSION=1.0.0"
set "SPEC_FILE=VoxelCraft.spec"
set "BUILD_DIR=build"
set "DIST_DIR=dist"
set "INSTALLER_DIR=installer"
set "VENV_DIR=venv"
set "INNO_SETUP_PATH="

echo ============================================
echo  Step 1: Checking Prerequisites
echo ============================================
echo.

REM Check Python
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)
python --version
echo.

REM Check/Create Virtual Environment
echo [2/7] Checking virtual environment...
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created.
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)
echo Virtual environment activated.
echo.

REM Check PyInstaller
echo [3/7] Checking PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller>=6.0
)
echo PyInstaller is ready.
echo.

REM Check Inno Setup
echo [4/7] Checking Inno Setup...
set INNO_SETUP_PATH=
if exist "C:\Progra~2\InnoSe~1\ISCC.exe" set INNO_SETUP_PATH=C:\Progra~2\InnoSe~1\ISCC.exe
if exist "C:\Progra~1\InnoSe~1\ISCC.exe" set INNO_SETUP_PATH=C:\Progra~1\InnoSe~1\ISCC.exe
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set INNO_SETUP_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe

if "%INNO_SETUP_PATH%"=="" (
    echo [WARNING] Inno Setup 6 not found!
    echo.
    echo Please install Inno Setup 6 from:
    echo https://jrsoftware.org/isdl.php
    echo.
    echo You can still build the executable, but the installer will not be created.
    echo.
    set /p CONTINUE="Continue with executable build only? (Y/N): "
    if /i not "%CONTINUE%"=="Y" (
        pause
        exit /b 1
    )
) else (
    echo Inno Setup found at:
    echo %INNO_SETUP_PATH%
)
echo.

REM Check logo file
echo [5/7] Checking logo files...
if not exist "%INSTALLER_DIR%\setup_assets\logo.bmp" (
    echo [WARNING] Logo BMP file not found in installer\setup_assets\
    echo The installer will use default branding.
    echo.
    echo To add custom branding, create:
    echo   - installer\setup_assets\logo.bmp (500x300 pixels for sidebar)
    echo   - installer\setup_assets\logo.ico (for setup icon)
) else (
    echo Logo files found.
)
echo.

REM Check license file
echo [6/7] Checking license file...
if not exist "%INSTALLER_DIR%\setup_assets\LICENSE.txt" (
    echo [WARNING] LICENSE.txt not found!
    echo Creating default license file...
    echo Voxel Craft Software License > "%INSTALLER_DIR%\setup_assets\LICENSE.txt"
    echo Copyright ^(c^) 2024 Voxel Craft >> "%INSTALLER_DIR%\setup_assets\LICENSE.txt"
) else (
    echo License file found.
)
echo.

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo Dependencies installed.
echo.

echo ============================================
echo  Step 2: Cleaning Previous Builds
echo ============================================
echo.

if exist %BUILD_DIR% (
    echo Removing old build directory...
    rmdir /s /q %BUILD_DIR% 2>nul
    timeout /t 1 /nobreak >nul
    rmdir /s /q %BUILD_DIR% 2>nul
)

if exist %DIST_DIR% (
    echo Removing old dist directory...
    rmdir /s /q %DIST_DIR% 2>nul
    timeout /t 1 /nobreak >nul
    rmdir /s /q %DIST_DIR% 2>nul
)

if exist "%INSTALLER_DIR%\output" (
    echo Removing old installer output...
    rmdir /s /q "%INSTALLER_DIR%\output" 2>nul
)

echo Clean complete.
echo.

REM Create .env from .env.example if it doesn't exist
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy .env.example .env >nul
    )
)

echo ============================================
echo  Step 3: Building Executable
echo ============================================
echo.
echo This may take 30-60 minutes depending on your system...
echo Please be patient and do not close this window.
echo.

python -m PyInstaller --clean --noconfirm %SPEC_FILE%

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Executable build failed!
    echo Please check the error messages above.
    echo.
    pause
    exit /b 1
)

if not exist "%DIST_DIR%\%APP_NAME%\%APP_NAME%.exe" (
    if not exist "%DIST_DIR%\%APP_NAME%.exe" (
        echo.
        echo [ERROR] Executable not found after build!
        echo Expected: %DIST_DIR%\%APP_NAME%\%APP_NAME%.exe or %DIST_DIR%\%APP_NAME%.exe
        echo.
        pause
        exit /b 1
    )
)

if exist "%DIST_DIR%\%APP_NAME%\%APP_NAME%.exe" (
    set "EXE_PATH=%DIST_DIR%\%APP_NAME%\%APP_NAME%.exe"
) else (
    set "EXE_PATH=%DIST_DIR%\%APP_NAME%.exe"
)

for %%I in ("%EXE_PATH%") do (
    set "EXE_SIZE=%%~zI"
)
echo.
echo Executable build successful!
echo Location: %EXE_PATH%
echo.

REM Build installer only if Inno Setup is available
if not defined INNO_SETUP_PATH goto :skip_installer

echo ============================================
echo  Step 4: Building Installer
echo ============================================
echo.
echo This may take 5-10 minutes...
echo.

cd %INSTALLER_DIR%
"%INNO_SETUP_PATH%" /Q "VoxelCraft.iss"
set BUILD_RESULT=%errorlevel%
cd ..

if %BUILD_RESULT% neq 0 (
    echo.
    echo [ERROR] Installer build failed!
    echo Please check the error messages above.
    echo.
    pause
    exit /b 1
)

if not exist "%INSTALLER_DIR%\output\VoxelCraft_Setup_v%APP_VERSION%.exe" (
    echo.
    echo [ERROR] Installer file not found after build!
    echo.
    pause
    exit /b 1
)

for %%I in ("%INSTALLER_DIR%\output\VoxelCraft_Setup_v%APP_VERSION%.exe") do (
    set "INSTALLER_SIZE=%%~zI"
)

echo.
echo Installer build successful!
echo.

echo ============================================
echo  Step 5: Creating Distribution Package
echo ============================================
echo.

set "PACKAGE_NAME=VoxelCraft_v%APP_VERSION%_Complete"

if exist "%PACKAGE_NAME%.zip" del /f "%PACKAGE_NAME%.zip"

powershell -Command "Compress-Archive -Path '%INSTALLER_DIR%\output\VoxelCraft_Setup_v%APP_VERSION%.exe' -DestinationPath '%PACKAGE_NAME%.zip' -Force"

if errorlevel 1 (
    echo [WARNING] Failed to create ZIP package.
    echo You can manually distribute the installer file.
) else (
    for %%I in ("%PACKAGE_NAME%.zip") do (
        set "ZIP_SIZE=%%~zI"
    )
    echo Distribution package created: %PACKAGE_NAME%.zip
)
echo.

goto :build_complete

:skip_installer
echo ============================================
echo  Step 4: Skipping Installer Build
echo ============================================
echo.
echo Inno Setup was not found. Only the executable was built.
echo.

:build_complete

echo ============================================
echo  Build Complete! 
echo ============================================
echo.
echo Summary:
echo   Application: %APP_NAME% v%APP_VERSION%
echo.
echo   Executable:
echo     File: %DIST_DIR%\%APP_NAME%.exe
echo.

if defined INNO_SETUP_PATH (
    echo   Installer:
    echo     File: %INSTALLER_DIR%\output\VoxelCraft_Setup_v%APP_VERSION%.exe
    echo.
    echo   Distribution:
    echo     File: %PACKAGE_NAME%.zip
    echo.
    echo Installer Features:
    echo   [x] Professional Antigravity style setup wizard with custom branding
    echo   [x] License agreement acceptance required
    echo   [x] Custom installation directory selection
    echo   [x] Desktop shortcut option
    echo   [x] Launch after installation checkbox
    echo   [x] Automatic upgrade detection
    echo   [x] Windows registry integration
    echo   [x] Clean uninstall support
    echo.
    echo Next Steps:
    echo   1. Test the installer: %INSTALLER_DIR%\output\VoxelCraft_Setup_v%APP_VERSION%.exe
    echo   2. Verify all features work correctly
    echo   3. Upload to your distribution server
    echo.
) else (
    echo Next Steps:
    echo   1. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo   2. Run this script again to create the installer
    echo   3. Or distribute the executable directly
    echo.
)

pause
