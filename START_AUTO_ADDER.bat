@echo off
setlocal

cd /d "%~dp0"

if not exist "engine\auto_adder_engine.py" (
  echo engine\auto_adder_engine.py was not found next to the app.
  pause
  exit /b 1
)

if exist "python\python.exe" (
  goto :run_app
)

if not exist ".venv\Scripts\python.exe" (
  echo Portable Python was not found. Installing local dependencies...
  call install_deps.bat
  if errorlevel 1 (
    echo.
    echo Could not install dependencies. Install Python 3.10+ with Add Python to PATH, or use the portable release zip.
    pause
    exit /b 1
  )
)

:run_app
if exist "AutoAdder.exe" (
  start "" "AutoAdder.exe"
) else if exist "cpp\build\AutoAdder.exe" (
  start "" "cpp\build\AutoAdder.exe"
) else (
  echo AutoAdder.exe was not found.
  pause
  exit /b 1
)

endlocal
