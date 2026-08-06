@echo off
setlocal
cd /d "%~dp0"

if exist "..\python\python.exe" (
  "..\python\python.exe" "run_check.py"
  goto :done
)

if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" "run_check.py"
  goto :done
)

python "run_check.py"

:done
endlocal
