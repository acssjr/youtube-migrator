@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python "%~dp0run_downloads.py"
) else (
    py -3 "%~dp0run_downloads.py"
)
if errorlevel 1 pause
