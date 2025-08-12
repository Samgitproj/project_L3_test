@echo off
setlocal EnableDelayedExpansion

rem Rootpad bepalen
set "ROOTDIR=%~dp0"
cd /d "%ROOTDIR%"

rem Pad naar 'documents'-map
set "DOCFOLDER=%ROOTDIR%documents"
if not exist "%DOCFOLDER%" (
    mkdir "%DOCFOLDER%"
)

rem Uitvoerbestand instellen
set "OUTFILE=%DOCFOLDER%\ProjectStructure.txt"
if exist "%OUTFILE%" del "%OUTFILE%"

rem Kopregel toevoegen
echo Projectstructuur van: %ROOTDIR% > "%OUTFILE%"
echo. >> "%OUTFILE%"

rem Start met bestanden in root tonen
call :ListFolder "%ROOTDIR%" >> "%OUTFILE%"

goto :eof

:ListFolder
set "FOLDER=%~1"
pushd "%FOLDER%" >nul

rem Bestanden in root tonen
for /f "delims=" %%F in ('dir /b /a-d') do (
    echo %%F
)

rem Mappen overlopen
for /f "delims=" %%D in ('dir /b /ad') do (
    if /i "%%D"=="backup" (
        echo %%D
    ) else (
        call :Recurse "%%D" 1
    )
)

popd >nul
exit /b

:Recurse
set "SUBFOLDER=%~1"
set "LEVEL=%~2"

rem Inspringing maken
set "INDENT="
for /L %%I in (1,1,%LEVEL%) do set "INDENT=!INDENT!    "

echo !INDENT!Directory: %SUBFOLDER%

pushd "%SUBFOLDER%" >nul

for /f "delims=" %%F in ('dir /b /a-d') do (
    echo !INDENT!    %%F
)

for /f "delims=" %%D in ('dir /b /ad') do (
    set /a NEXTLEVEL=%LEVEL%+1
    call :Recurse "%%D" !NEXTLEVEL!
)

popd >nul
exit /b
