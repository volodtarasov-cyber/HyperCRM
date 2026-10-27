@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0..\..\venv\Scripts\python.exe" build.py
if errorlevel 1 pause & exit /b 1
start "" "%~dp0out\index.html"
