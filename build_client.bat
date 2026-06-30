@echo off
REM ================================================================
REM  Compile Windows client  in a .exe ( dist\  folder).
REM  You need Python installed. To change icon replace
REM  icon.ico with your icon and run this file.
REM ================================================================
cd /d "%~dp0"

echo Installing/updating dependencies...
python -m pip install --upgrade pyinstaller requests pyperclip pystray pillow keyboard

echo.
echo Compiling...
python -m PyInstaller --noconfirm --onefile --windowed ^
  --icon icon.ico --name "Clipboard Bridge" ^
  --add-data "icon.ico;." ^
  --hidden-import pystray._win32 ^
  --collect-submodules keyboard ^
  clipboard_bridge_windows.py

echo.
echo Done. executable file directory:  dist\Clipboard Bridge.exe
pause
