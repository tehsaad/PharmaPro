@echo off
REM Build PharmaPro on Windows. Run from the project folder:
REM     packaging\build_windows.bat            -> dist\PharmaPro.exe           (single file, recommended)
REM     packaging\build_windows.bat onedir     -> dist\PharmaPro\PharmaPro.exe (folder, starts faster)
setlocal
cd /d "%~dp0\.."

set SPEC=PharmaPro-onefile.spec
if /i "%1"=="onedir" set SPEC=PharmaPro.spec

if not exist .venv (
    py -3 -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error

python -m pytest -q || goto :error
pyinstaller --noconfirm --clean %SPEC% || goto :error

echo.
if "%SPEC%"=="PharmaPro.spec" (
    echo Build complete: dist\PharmaPro\PharmaPro.exe  - copy the whole dist\PharmaPro folder.
) else (
    echo Build complete: dist\PharmaPro.exe  - a single file, copy it anywhere and double-click.
)
exit /b 0

:error
echo.
echo Build failed. See the messages above.
exit /b 1
