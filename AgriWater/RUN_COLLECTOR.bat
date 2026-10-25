@echo off
setlocal
cd /d "%~dp0"
echo =====================================================
echo AgriWater Intelligence - Kafr El Sheikh Data Collector
echo =====================================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found. Install Python 3.11+ from https://www.python.org/downloads/
  echo Ensure "Add Python to PATH" is selected, then run this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  py -3 -m venv .venv
  if errorlevel 1 goto :fail
)
echo Installing/checking required libraries...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo Starting collector...
".venv\Scripts\python.exe" collect.py
echo.
echo Finished. Check reports\latest_report.json and logs\collector.log
pause
exit /b 0
:fail
echo Setup failed. Check the error above and internet access.
pause
exit /b 1
