@echo off
rem --------------------------------------------------
rem start_qtdesigner.bat
rem Zoekt recursief naar designer.exe onder C:\QTDesigner
rem en start de eerste match.
rem --------------------------------------------------

set "searchRoot=C:\QTDesigner"

rem Zoek naar designer.exe (dir /s /b geeft volledige paden)
for /f "usebackq delims=" %%a in (`
    dir "%searchRoot%\designer.exe" /s /b 2^>nul
`) do (
    echo Found Qt Designer at %%a
    start "" "%%a"
    goto :EOF
)

echo Fout: geen designer.exe gevonden onder %searchRoot%
pause
