@echo off
REM Double-click this file to open the Cart Recovery Agent app (chat + charts) in your browser.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run agent_app.py
pause
