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

echo [1/6] Installing build dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pyinstaller
"%PYTHON_EXE%" -m pip install -r requirements-client.txt
if errorlevel 1 exit /b 1

echo [2/6] Building the portable Windows executable...
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

echo [3/6] Building the Windows installer...
"%ISCC%" /DMyAppVersion=%VERSION% "Clipboard_Bridge_setup.iss"
if errorlevel 1 exit /b 1

echo [4/6] Preparing the complete GitHub release folder...
set "RELEASE_DIR=Output\Clipboard.Bridge.Release.V%VERSION%"
if exist "%RELEASE_DIR%" rmdir /S /Q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"
copy /Y "Output\Clipboard.Bridge.Portable.Windows.x64.V%VERSION%.exe" "%RELEASE_DIR%\" >nul
copy /Y "Output\Clipboard.Bridge_windows_client_and_server_setup_x64_V%VERSION%.exe" "%RELEASE_DIR%\" >nul
copy /Y "Iphone Shortcuts\Load Clipboard.shortcut" "%RELEASE_DIR%\Load.Clipboard.shortcut" >nul
copy /Y "Iphone Shortcuts\Download Clipboard.shortcut" "%RELEASE_DIR%\Download.Clipboard.shortcut" >nul
copy /Y "clipboard_bridge-Server.py" "%RELEASE_DIR%\" >nul
copy /Y "Dockerfile" "%RELEASE_DIR%\" >nul
copy /Y "docker-compose.yml" "%RELEASE_DIR%\" >nul
copy /Y "compose.yaml" "%RELEASE_DIR%\" >nul
copy /Y "requirements-server.txt" "%RELEASE_DIR%\" >nul
copy /Y "requirements-client.txt" "%RELEASE_DIR%\" >nul
copy /Y "pytest.ini" "%RELEASE_DIR%\" >nul
copy /Y "clipboard_bridge_windows.py" "%RELEASE_DIR%\" >nul
copy /Y "build_client.bat" "%RELEASE_DIR%\" >nul
copy /Y "build_windows_release.bat" "%RELEASE_DIR%\" >nul
copy /Y "Clipboard_Bridge_setup.iss" "%RELEASE_DIR%\" >nul
copy /Y "windows_version_info.txt" "%RELEASE_DIR%\" >nul
copy /Y "VERSION" "%RELEASE_DIR%\" >nul
mkdir "%RELEASE_DIR%\scripts"
copy /Y "scripts\release_metadata.py" "%RELEASE_DIR%\scripts\" >nul
copy /Y "icon.ico" "%RELEASE_DIR%\" >nul
copy /Y ".env.example" "%RELEASE_DIR%\clipboard-bridge.env.example" >nul
copy /Y "GUIDE.md" "%RELEASE_DIR%\Clipboard.Bridge.GUIDE.md" >nul
copy /Y "README.md" "%RELEASE_DIR%\README.md" >nul
copy /Y "README.it.md" "%RELEASE_DIR%\README.it.md" >nul
copy /Y "DOCKER.md" "%RELEASE_DIR%\" >nul
copy /Y "CODE_SIGNING.md" "%RELEASE_DIR%\" >nul
copy /Y "SECURITY.md" "%RELEASE_DIR%\" >nul
copy /Y "CHANGELOG.md" "%RELEASE_DIR%\" >nul
copy /Y "CONTRIBUTING.md" "%RELEASE_DIR%\" >nul
copy /Y "LICENSE" "%RELEASE_DIR%\" >nul
xcopy /E /I /Y "docs" "%RELEASE_DIR%\docs" >nul
mkdir "%RELEASE_DIR%\tests"
copy /Y "tests\*.py" "%RELEASE_DIR%\tests\" >nul
if errorlevel 1 exit /b 1

echo [5/6] Creating the source and server bundle...
powershell -NoProfile -Command "$source = '%RELEASE_DIR%'; $staging = 'Output\Clipboard.Bridge.Source.and.Server.V%VERSION%'; $destination = $staging + '.zip'; if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }; if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Force }; New-Item -ItemType Directory -Path $staging | Out-Null; Get-ChildItem -LiteralPath $source | Where-Object { $_.Extension -ne '.exe' } | Copy-Item -Destination $staging -Recurse; Compress-Archive -LiteralPath $staging -DestinationPath $destination -CompressionLevel Optimal; Remove-Item -LiteralPath $staging -Recurse -Force"
if errorlevel 1 exit /b 1

powershell -NoProfile -Command "$items = Get-Item -LiteralPath 'Output\Clipboard.Bridge.Portable.Windows.x64.V%VERSION%.exe','Output\Clipboard.Bridge_windows_client_and_server_setup_x64_V%VERSION%.exe','Output\Clipboard.Bridge.Source.and.Server.V%VERSION%.zip'; $lines = $items | ForEach-Object { '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant(), $_.Name }; Set-Content -LiteralPath 'Output\SHA256SUMS.V%VERSION%.txt' -Value $lines -Encoding ascii"
if errorlevel 1 exit /b 1
copy /Y "Output\SHA256SUMS.V%VERSION%.txt" "%RELEASE_DIR%\" >nul
if errorlevel 1 exit /b 1

echo [6/6] Build complete.
echo Portable: Output\Clipboard.Bridge.Portable.Windows.x64.V%VERSION%.exe
echo Installer: Output\Clipboard.Bridge_windows_client_and_server_setup_x64_V%VERSION%.exe
echo Source bundle: Output\Clipboard.Bridge.Source.and.Server.V%VERSION%.zip
echo Checksums: Output\SHA256SUMS.V%VERSION%.txt
echo Complete release assets: %RELEASE_DIR%
exit /b 0
