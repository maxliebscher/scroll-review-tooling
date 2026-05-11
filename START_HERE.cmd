@echo off
setlocal

cd /d "%~dp0"
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
echo.
echo Step 1: checking local setup...
call CHECK_LOCAL_SETUP.cmd /nopause %START_ARGS%
if errorlevel 1 (
  echo.
  echo Setup is blocked. Open demo\out\operator_doctor.html for the exact fix.
  if not defined NO_PAUSE pause
  exit /b 1
)

echo.
echo Step 2: starting the local operator app...
if defined NO_OPEN (
  call RUN_LOCAL_OPERATOR.cmd %START_ARGS%
) else (
  call RUN_LOCAL_APP.cmd %START_ARGS%
)
if errorlevel 1 (
  echo.
  echo Local operator is blocked. Open demo\out\operator.html and demo\out\local_operator.json for details.
  if not defined NO_PAUSE pause
  exit /b 1
)

echo.
if defined NO_OPEN (
  echo Done. Generated reports are in demo\out.
) else (
  echo Done. The local app runs on 127.0.0.1. Close this window to stop it.
)
if not defined NO_PAUSE pause
