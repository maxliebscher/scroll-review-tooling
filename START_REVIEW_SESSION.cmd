@echo off
setlocal

cd /d "%~dp0"

echo Creating local no-claim review session...
python scripts\start_session.py --demo %*
if errorlevel 1 (
  echo.
  echo Review session is blocked. See the printed session status for details.
  exit /b 1
)

echo.
echo Review session is ready. Open the session out folder shown above.

endlocal
