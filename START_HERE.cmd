@echo off
setlocal

cd /d "%~dp0"
if not exist demo\out mkdir demo\out
set START_LOG=demo\out\start_here.log
> "%START_LOG%" echo Scroll Review Tooling local start
set NO_PAUSE=
if /I "%~1"=="/nopause" (
  set NO_PAUSE=1
  shift
)
set NO_OPEN=
if /I "%~1"=="/noopen" (
  set NO_OPEN=1
  shift
)
set START_ARGS=
:collect_args
if "%~1"=="" goto run_start
if /I "%~1"=="/noopen" (
  set NO_OPEN=1
  shift
  goto collect_args
)
if /I "%~1"=="/nopause" (
  set NO_PAUSE=1
  shift
  goto collect_args
)
set START_ARGS=%START_ARGS% "%~1"
shift
goto collect_args
:run_start

echo Scroll Review Tooling local start
echo Primary Windows entry point for the local desktop operator flow.
echo Log: %START_LOG%
echo.
python --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer, then run START_HERE.cmd again.
  echo Download Python from python.org, then reopen this file.
  >> "%START_LOG%" echo Python was not found on PATH.
  if not defined NO_PAUSE pause
  exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do >> "%START_LOG%" echo Python: %%v
if not defined NO_OPEN (
  python -c "import socket; s=socket.socket(); s.settimeout(.25); raise SystemExit(1 if s.connect_ex(('127.0.0.1',8765)) == 0 else 0)" >nul 2>nul
  if errorlevel 1 (
    echo Port 8765 already has a local service on it. Close the existing Scroll Review app window, or run scripts\operator_server.py with another --port.
    echo If you already have the app open, use that browser tab instead of starting a second copy.
    >> "%START_LOG%" echo Port 8765 was already in use.
    if not defined NO_PAUSE pause
    exit /b 1
  )
)
echo Step 1: checking local setup...
>> "%START_LOG%" echo Step 1: checking local setup
call CHECK_LOCAL_SETUP.cmd /nopause %START_ARGS%
if errorlevel 1 (
  echo.
  echo Setup is blocked. Open demo\out\operator_doctor.html for the exact fix.
  >> "%START_LOG%" echo Setup blocked. See demo\out\operator_doctor.html.
  if not defined NO_PAUSE pause
  exit /b 1
)

echo.
echo Step 2: starting the local operator app...
>> "%START_LOG%" echo Step 2: starting local operator app
if defined NO_OPEN (
  call RUN_LOCAL_OPERATOR.cmd %START_ARGS%
) else (
  echo If the browser does not open, manually open http://127.0.0.1:8765/
  echo This local address is the app. Nothing is uploaded.
  >> "%START_LOG%" echo Browser should open http://127.0.0.1:8765/
  call RUN_LOCAL_APP.cmd %START_ARGS%
)
if errorlevel 1 (
  echo.
  echo Local operator is blocked. Check demo\out\start_here.log, then open demo\out\operator.html and demo\out\local_operator.json for details.
  >> "%START_LOG%" echo Local operator blocked.
  if not defined NO_PAUSE pause
  exit /b 1
)

echo.
if defined NO_OPEN (
  echo Done. Generated reports are in demo\out.
) else (
  echo Done. The local app runs on 127.0.0.1. Close this window to stop it.
  echo Browser did not open? Go to http://127.0.0.1:8765/
)
if not defined NO_PAUSE pause
