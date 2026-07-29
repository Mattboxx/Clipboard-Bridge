@echo off
setlocal
cd /d "%~dp0"

set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=2.0.0"

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

echo [1/4] Installing build dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pyinstaller requests pyperclip pystray pillow keyboard
if errorlevel 1 exit /b 1

echo [2/4] Building the portable Windows executable...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean ^
  --icon icon.ico --name "Clipboard Bridge" ^
  --add-data "icon.ico;." ^
  --hidden-import pystray._win32 ^
  --collect-submodules keyboard ^
  --onefile --windowed clipboard_bridge_windows.py
if errorlevel 1 exit /b 1

if not exist "Output" mkdir "Output"
copy /Y "dist\Clipboard Bridge.exe" "Output\Clipboard.Bridge.Portable.Windows.x64.V%VERSION%.exe" >nul
if errorlevel 1 exit /b 1

set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 was not found.
  echo Install it with: winget install --id JRSoftware.InnoSetup --exact
  exit /b 1
)

echo [3/4] Building the Windows installer...
"%ISCC%" /DMyAppVersion=%VERSION% "Clipboard_Bridge_setup.iss"
if errorlevel 1 exit /b 1

echo [4/4] Build complete.
echo Portable: Output\Clipboard.Bridge.Portable.Windows.x64.V%VERSION%.exe
echo Installer: Output\Clipboard.Bridge_windows_client_and_server_setup_x64_V%VERSION%.exe
exit /b 0
