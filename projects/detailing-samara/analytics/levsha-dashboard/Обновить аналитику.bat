@echo off
chcp 65001 >nul
cd /d "%~dp0"

set ROOT=%~dp0..\..\..\..
"%ROOT%\.tools\venv\Scripts\python.exe" "%ROOT%\.tools\projects\detailing-samara\analytics\levsha-dashboard-update.py" --project "%~dp0."

if errorlevel 1 goto failed
start "" "%~dp0dashboard\index.html"
echo.
echo OK. Dashboard updated and opened in browser.
goto end

:failed
echo.
echo Update stopped. See details above and in logs\update.log

:end
echo.
pause
