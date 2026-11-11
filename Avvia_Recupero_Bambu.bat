@echo off
title Bambu Rescue - Recupero Progetti Bambu Studio 3MF
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo       BAMBU RESCUE - Recupero Progetti 3MF da Crash
echo ========================================================
echo.
echo Avvio dell'interfaccia grafica in corso...

if exist "%~dp0BambuRescue.exe" (
    start "" "%~dp0BambuRescue.exe" %*
    exit
)

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw "%~dp0recupero_bambu_3mf_gui.py" %*
    exit
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python "%~dp0recupero_bambu_3mf_gui.py" %*
    exit
)

echo [ERRORE] Python non e stato trovato nel sistema.
echo Assicurati che Python sia installato e aggiunto al PATH,
echo oppure utilizza l'eseguibile standalone 'BambuRescue.exe'.
echo.
pause
