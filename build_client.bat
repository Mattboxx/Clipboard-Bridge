@echo off
REM ================================================================
REM  Compila il client Windows in un singolo .exe (cartella dist\).
REM  Richiede Python installato. Per cambiare icona sostituisci
REM  icon.ico con la tua e rilancia questo file.
REM ================================================================
cd /d "%~dp0"

echo Installazione/aggiornamento dipendenze...
python -m pip install --upgrade pyinstaller requests pyperclip pystray pillow keyboard

echo.
echo Compilazione...
python -m PyInstaller --noconfirm --onefile --windowed ^
  --icon icon.ico --name "Clipboard Bridge" ^
  --add-data "icon.ico;." ^
  --hidden-import pystray._win32 ^
  --collect-submodules keyboard ^
  clipboard_bridge_windows.py

echo.
echo Fatto. Eseguibile in:  dist\Clipboard Bridge.exe
pause
