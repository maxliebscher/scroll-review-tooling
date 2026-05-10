@echo off
setlocal

cd /d "%~dp0"

echo Running local no-claim operator checks...
python scripts\local_operator.py
if errorlevel 1 (
  echo.
  echo Local operator is blocked. See demo\out\local_operator.json and demo\out\release_check.json for details.
  exit /b 1
)

echo.
echo Local operator is ready.
echo Open demo\out\operator.html first, then demo\out\dashboard.html.

endlocal
