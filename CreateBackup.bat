@echo off
REM --------------------------------------------------
REM CreateBackup.bat
REM Maakt een timestamped backup in de submap 'backup'
REM --------------------------------------------------
setlocal

REM Bepaal script-root (project-map), zonder trailing backslash
set "root=%~dp0"
if "%root:~-1%"=="\" set "root=%root:~0,-1%"

REM Genereer timestamp in ddMMyyHHmm-formaat
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format ddMMyyHHmm"') do set "ts=%%i"

REM Timestamp-folder maken onder backup (backup bestaat al)
set "dest=%root%\backup\%ts%"
md "%dest%" 2>nul

REM Kopieer alle items behalve de 'backup'-map
robocopy "%root%" "%dest%" /E /XD "%root%\backup" >nul

endlocal
