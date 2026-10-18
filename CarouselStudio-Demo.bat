@echo off
rem Demo mode: the full UI with placeholder images and canned texts. No Claude or ChatGPT calls.
rem Uses a separate demo project folder so real data is never touched.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call "%~dp0CarouselStudio.bat" --help >nul
".venv\Scripts\python.exe" -m tests.make_demo "%~dp0_demo"
".venv\Scripts\python.exe" -m app --fake --root "%~dp0_demo" --port 8766
if errorlevel 1 pause
