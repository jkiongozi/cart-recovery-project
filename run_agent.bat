@echo off
REM Double-click this file to start the Cart Recovery Agent.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python agent.py
pause
