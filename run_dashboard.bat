@echo off
REM Double-click this file to open the Cart Recovery dashboard in your browser.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run dashboard.py
pause
