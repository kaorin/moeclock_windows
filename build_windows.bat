@echo off
chcp 65001 >nul
setlocal
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name moeclock ^
  --add-data "skins;skins" ^
  --add-data "sound;sound" ^
  --add-data "moeclock.png;." ^
  --collect-all PySide6.QtSvg ^
  moeclock.py
echo.
echo Build finished. EXE: dist\moeclock.exe
pause
