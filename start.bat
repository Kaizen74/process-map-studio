@echo off
rem Process Map Studio: start the app on Windows. Close this window to stop it. See README.md.
setlocal
cd /d "%~dp0"
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY (
  python --version 2>nul | findstr /b /c:"Python 3.12" >nul && set "PY=python"
)
if not defined PY (
  echo Python 3.12 was not found. Install it from python.org ^(README step 1^), then run setup.bat.
  pause
  exit /b 1
)
title Process Map Studio
%PY% scripts\start.py %*
set "STATUS=%ERRORLEVEL%"
if not "%STATUS%"=="0" (
  echo.
  pause
)
exit /b %STATUS%
