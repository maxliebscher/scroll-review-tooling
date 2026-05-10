@echo off
setlocal

cd /d "%~dp0"

echo Running local no-claim dashboard checks...
python scripts\local_dashboard.py
if errorlevel 1 (
  echo.
  echo Local dashboard is blocked. See demo\out\local_dashboard.json and demo\out\release_check.json for details.
  exit /b 1
)

echo.
echo Local dashboard is ready.
echo Open demo\out\dashboard.html in your browser.

endlocal
