@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" dayboard.py
if errorlevel 1 pause
