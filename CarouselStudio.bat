@echo off
setlocal
cd /d "%~dp0"
title Carousel Studio

if not exist ".venv\Scripts\python.exe" (
  echo Creating the Python environment ^(first run only^)...
  python -m venv .venv
  if errorlevel 1 (
    echo.
    echo Python was not found. Install Python 3.11+ from https://www.python.org and run this file again.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -c "import flask, playwright, PIL" 2>nul
if errorlevel 1 (
  echo Installing dependencies ^(first run only^)...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
  if errorlevel 1 (
    echo Installing dependencies failed.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m app %*
if errorlevel 1 pause
