@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\serve_full.py --light-bias inf %*
) else (
    python scripts\serve_full.py --light-bias inf %*
)
pause
