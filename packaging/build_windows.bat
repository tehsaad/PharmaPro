@echo off
REM Build PharmaPro.exe on Windows. Run from the project folder:  packaging\build_windows.bat
setlocal
cd /d "%~dp0\.."

if not exist .venv (
    py -3 -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error

python -m pytest -q || goto :error
pyinstaller --noconfirm --clean PharmaPro.spec || goto :error

echo.
echo Build complete: dist\PharmaPro\PharmaPro.exe
echo Copy the whole dist\PharmaPro folder to the pharmacy computer.
exit /b 0

:error
echo.
echo Build failed. See the messages above.
exit /b 1
