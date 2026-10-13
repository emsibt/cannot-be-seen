@echo off
rem Launch cannot-be-seen with no console window.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo No .venv found. Run setup.cmd first.
    pause
    exit /b 1
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0run.pyw"
exit /b 0
