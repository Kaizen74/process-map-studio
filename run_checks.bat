@echo off
rem Runs ./run_checks.sh on Windows through Git Bash (installed with Git for Windows). Developers only.
setlocal
cd /d "%~dp0"
set "BASH="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH (
  echo Git Bash was not found. Install Git for Windows from git-scm.com, then run this again.
  exit /b 1
)
"%BASH%" run_checks.sh
exit /b %ERRORLEVEL%
