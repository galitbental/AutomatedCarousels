@echo off
rem Runs the automated test suite (unit, regression, API, end-to-end, UI).
rem   RunTests.bat                 default suite
rem   RunTests.bat -m live         live smoke tests (real Claude / ChatGPT, costs money)
rem   set UPDATE_GOLDEN=1 ^& RunTests.bat   regenerate regression baselines on purpose
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pytest %*
pause
