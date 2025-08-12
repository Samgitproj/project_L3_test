@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
for %%I in ("%~dp0.") do set "PROJECT_NAME=%%~nI"
set "PY=C:\virt omgeving\%PROJECT_NAME%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ERROR] Venv Python niet gevonden: "%PY%"
  pause & exit /b 1
)
pushd "%PROJECT_ROOT%"
"%PY%" "%PROJECT_ROOT%ui2py_gui.py"
popd
