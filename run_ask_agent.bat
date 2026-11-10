@echo off
REM Double-click this file to ask the agent in your browser.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run ask_agent.py
pause
