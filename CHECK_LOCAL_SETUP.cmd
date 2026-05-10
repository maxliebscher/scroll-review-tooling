@echo off
setlocal
cd /d "%~dp0"
set NO_PAUSE=
if /I "%~1"=="/nopause" (
  set NO_PAUSE=1
  shift
)
set DOCTOR_ARGS=
:collect_args
if "%~1"=="" goto run_doctor
set DOCTOR_ARGS=%DOCTOR_ARGS% "%~1"
shift
goto collect_args
:run_doctor
echo Checking local Scroll Review operator setup...
python scripts\operator_doctor.py %DOCTOR_ARGS%
if errorlevel 1 (
  echo.
  echo Setup check found a blocker. Open demo\out\operator_doctor.html or demo\out\operator_doctor.md for the next step.
  if not defined NO_PAUSE pause
  exit /b 1
)
echo.
echo Setup check passed. Open demo\out\operator_doctor.html for details, then run OPEN_LOCAL_OPERATOR.cmd.
if not defined NO_PAUSE pause
