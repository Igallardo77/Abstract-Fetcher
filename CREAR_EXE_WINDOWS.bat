@echo off
setlocal
cd /d "%~dp0"
echo === Preparar AbstractFetcher.exe para Windows ===
echo La primera vez requiere Internet y Python 3.10 o posterior.
echo.
where py >nul 2>nul
if not errorlevel 1 (
    set "AF_PYTHON=py -3"
    goto found
)
where python >nul 2>nul
if not errorlevel 1 (
    set "AF_PYTHON=python"
    goto found
)
echo No se encontro Python. Instala Python para Windows desde python.org.
echo Incluye Tcl/Tk y marca Add Python to PATH. Despues vuelve a abrir este archivo.
pause
exit /b 1
:found
%AF_PYTHON% -c "import sys, tkinter, ssl; assert sys.version_info >= (3, 10), 'Se requiere Python 3.10 o posterior'; r=tkinter.Tk(); r.withdraw(); r.destroy()"
if errorlevel 1 goto failed
%AF_PYTHON% -m venv .build-env
if errorlevel 1 goto failed
".build-env\Scripts\python.exe" -m pip install "pyinstaller>=6,<7"
if errorlevel 1 goto failed
".build-env\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
".build-env\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name AbstractFetcher abstract_fetcher.py
if errorlevel 1 goto failed
if not exist "dist\AbstractFetcher.exe" goto failed
echo.
echo LISTO: el ejecutable esta en dist\AbstractFetcher.exe
echo Puedes copiar ese EXE a otra PC Windows compatible sin instalar Python.
echo Abrelo con doble clic para comprobar la interfaz y una busqueda real.
start "" explorer.exe "%CD%\dist"
pause
exit /b 0
:failed
echo.
echo No se pudo crear el ejecutable. Revisa el mensaje anterior.
echo Conserva esta ventana para identificar el problema.
pause
exit /b 1
