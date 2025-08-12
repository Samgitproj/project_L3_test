@echo off
setlocal

rem Projectroot = map van deze .bat
set "PROJECT_ROOT=%~dp0"

rem Projectnaam = naam van die map
for %%I in ("%~dp0.") do set "PROJECT_NAME=%%~nI"

rem Venv-pad volgens jouw standaard
set "PY=C:\virt omgeving\%PROJECT_NAME%\venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] Venv Python niet gevonden:
  echo   "%PY%"
  echo Maak eerst je venv op dit pad aan.
  pause
  exit /b 1
)

rem Optioneel: 1e argument = alternatief script, anders main.py (fallback naar src\main.py)
if "%~1"=="" (
  set "MAIN=%PROJECT_ROOT%main.py"
  if not exist "%MAIN%" if exist "%PROJECT_ROOT%src\main.py" set "MAIN=%PROJECT_ROOT%src\main.py"
) else (
  set "MAIN=%PROJECT_ROOT%%~1"
)

if not exist "%MAIN%" (
  echo [ERROR] Kon main-script niet vinden.
  echo Gezocht: "%MAIN%"
  pause
  exit /b 1
)

echo [INFO] Project: %PROJECT_NAME%
echo [INFO] Python : "%PY%"
echo [INFO] Script : "%MAIN%"
pushd "%PROJECT_ROOT%"
"%PY%" "%MAIN%"
set "ERR=%ERRORLEVEL%"
popd

exit /b %ERR%
