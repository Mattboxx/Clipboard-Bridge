@echo off
setlocal
cd /d "%~dp0"

set /p PROJECT_VERSION=<VERSION
set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=%PROJECT_VERSION%"
if not "%VERSION%"=="%PROJECT_VERSION%" (
  echo Requested version %VERSION% does not match VERSION %PROJECT_VERSION%.
  exit /b 1
)

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

echo [1/5] Installing build dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pyinstaller
"%PYTHON_EXE%" -m pip install -r requirements-client.txt
if errorlevel 1 exit /b 1

echo [2/5] Building the portable Windows executable...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean ^
  --icon icon.ico --name "Clipboard Bridge" ^
  --version-file windows_version_info.txt ^
  --add-data "icon.ico;." ^
  --add-data "VERSION;." ^
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

echo [3/5] Building the Windows installer...
"%ISCC%" /DMyAppVersion=%VERSION% "Clipboard_Bridge_setup.iss"
if errorlevel 1 exit /b 1

echo [4/5] Preparing the public GitHub release assets...
set "RELEASE_DIR=Output\Clipboard.Bridge.Release.V%VERSION%"
if exist "%RELEASE_DIR%" rmdir /S /Q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"
copy /Y "Output\Clipboard.Bridge.Portable.Windows.x64.V%VERSION%.exe" "%RELEASE_DIR%\" >nul
copy /Y "Output\Clipboard.Bridge_windows_client_and_server_setup_x64_V%VERSION%.exe" "%RELEASE_DIR%\" >nul
copy /Y "Iphone Shortcuts\Load Clipboard.shortcut" "%RELEASE_DIR%\iPhone.Load.Clipboard.shortcut" >nul
copy /Y "Iphone Shortcuts\Download Clipboard.shortcut" "%RELEASE_DIR%\iPhone.Download.Clipboard.shortcut" >nul
copy /Y "clipboard_bridge-Server.py" "%RELEASE_DIR%\" >nul
copy /Y "clipboard_bridge_windows.py" "%RELEASE_DIR%\" >nul
if exist "android\app\build\outputs\apk\release\app-release.apk" (
  copy /Y "android\app\build\outputs\apk\release\app-release.apk" "%RELEASE_DIR%\Clipboard.Bridge.Android.universal.V1.0.0-beta.10.apk" >nul
)
if errorlevel 1 exit /b 1

echo [5/5] Build complete.
echo Portable: Output\Clipboard.Bridge.Portable.Windows.x64.V%VERSION%.exe
echo Installer: Output\Clipboard.Bridge_windows_client_and_server_setup_x64_V%VERSION%.exe
echo Public release assets: %RELEASE_DIR%
exit /b 0
