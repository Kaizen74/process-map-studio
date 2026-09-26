@echo off
rem Process Map Studio: one-time setup for Windows (run again after every update). See README.md step 3.
setlocal
cd /d "%~dp0"
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY (
  python --version 2>nul | findstr /b /c:"Python 3.12" >nul && set "PY=python"
)
if not defined PY (
  echo Python 3.12 was not found.
  echo Install it: go to python.org, Downloads, download Python 3.12 for Windows, open the installer
  echo and tick "Add python.exe to PATH" on the first screen. Then double-click setup.bat again.
  pause
  exit /b 1
)
%PY% scripts\setup.py %*
set "STATUS=%ERRORLEVEL%"
echo.
pause
exit /b %STATUS%
