@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo  cannot-be-seen - setup
echo ==========================================
echo.

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

%PY% -c "import sys" >nul 2>nul
if errorlevel 1 goto :nopython

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto :oldpython

if exist ".venv\Scripts\python.exe" (
    echo Reusing the existing .venv
) else (
    echo Creating .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto :failed
)

echo Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Checking imports ...
".venv\Scripts\python.exe" -c "import webview, pystray, PIL; print('  ok')"
if errorlevel 1 goto :failed

echo.
echo ==========================================
echo  Ready. Double-click start.cmd to run it.
echo ==========================================
pause
exit /b 0

:nopython
echo Python 3 was not found.
echo.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during the install.
pause
exit /b 1

:oldpython
echo Python 3.10 or newer is required. Found:
%PY% -c "import sys; print(' ', sys.version)"
pause
exit /b 1

:failed
echo.
echo Setup failed - see the messages above.
pause
exit /b 1
