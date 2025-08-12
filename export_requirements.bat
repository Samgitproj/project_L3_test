@echo off
REM 🟡 Bepaal huidige projectmap en projectnaam
set "PROJECTDIR=%~dp0"
for %%F in ("%PROJECTDIR:~0,-1%") do set "PROJECTNAME=%%~nxF"

REM 🔵 Bepaal pad naar de virtuele omgeving
set "VENV=C:\virt omgeving\%PROJECTNAME%\venv"

REM 🔵 Pad naar de outputmap (in het project zelf)
set "OUTPUT=%PROJECTDIR%documents"

REM 🟢 Maak de outputmap aan indien nodig
if not exist "%OUTPUT%" (
    mkdir "%OUTPUT%"
)

REM 🔴 Genereer requirements.txt (overschrijft altijd)
"%VENV%\Scripts\python.exe" -m pip freeze > "%OUTPUT%\requirements.txt"

echo.
echo ✅ requirements.txt aangemaakt in %OUTPUT%
pause
