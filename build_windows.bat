@echo off
echo ==========================================
echo MPC Sampler Windows Build Script
echo ==========================================
echo.

echo [1/3] Checking Python installation...
python --version
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)
echo.

echo [2/3] Installing required libraries...
python -m pip install --upgrade pip
python -m pip install pygame PyQt5 pyinstaller
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to install libraries.
    pause
    exit /b 1
)
echo.

echo [3/3] Building executable with PyInstaller...
python -m PyInstaller --noconfirm mpc_sampler.spec
if %ERRORLEVEL% neq 0 (
    echo Error: Build failed.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Build Completed Successfully!
echo The executable is in the "dist" folder.
echo ==========================================
pause
