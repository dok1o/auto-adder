@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>&1 && (
  py -3 -m venv .venv
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  goto :done
)

where python >nul 2>&1 && (
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  goto :done
)

echo Python 3 не найден. Установите Python 3 с python.org
exit /b 1

:done
echo.
echo Зависимости установлены.
echo Для OCR также установите Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
echo Для штрихкодов на Windows может понадобиться zbar DLL для pyzbar.
endlocal
