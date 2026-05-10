@echo off
setlocal

cd /d "%~dp0"

call RUN_LOCAL_OPERATOR.cmd
if errorlevel 1 (
  exit /b 1
)

start "" "demo\out\operator.html"

endlocal
