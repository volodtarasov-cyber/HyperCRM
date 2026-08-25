@echo off
setlocal
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-hypercrm.ps1"
set "SYNC_EXIT=%ERRORLEVEL%"
echo.
if not "%SYNC_EXIT%"=="0" (
  echo Sync failed. Keep the error text before closing this window.
) else (
  echo Sync complete. You can close this window.
)
pause >nul
exit /b %SYNC_EXIT%
