@echo off
REM Build the portable Windows client in dist\.
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
  echo Python was not found.
  echo Install it with: winget install --id Python.Python.3.12 --exact
  exit /b 1
)

echo Preparing version metadata...
"%PYTHON_EXE%" scripts\release_metadata.py --write
if errorlevel 1 exit /b 1

echo Installing/updating dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pyinstaller
"%PYTHON_EXE%" -m pip install -r requirements-client.txt
if errorlevel 1 exit /b 1

echo.
echo Compiling...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --icon icon.ico --name "Clipboard Bridge" ^
  --version-file windows_version_info.txt ^
  --add-data "icon.ico;." ^
  --add-data "VERSION;." ^
  --hidden-import pystray._win32 ^
  --collect-submodules keyboard ^
  clipboard_bridge_windows.py
if errorlevel 1 exit /b 1

echo.
echo Done. Executable: dist\Clipboard Bridge.exe
pause
