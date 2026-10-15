@echo off
setlocal
cd /d "%~dp0"
if exist "dist\AbstractFetcher.exe" (
    start "" "dist\AbstractFetcher.exe"
    exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 abstract_fetcher.py
    if errorlevel 1 goto failed
    exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
    python abstract_fetcher.py
    if errorlevel 1 goto failed
    exit /b 0
)
:failed
echo.
echo No se pudo abrir la aplicacion.
echo Necesitas Python 3.10 o posterior con Tcl/Tk, o el EXE generado.
echo Consulta LEEME.md para preparar el ejecutable.
pause
exit /b 1
