@echo off
chcp 65001 >nul
if not exist .venv\Scripts\python.exe (
  echo Environnement Python introuvable. Lance d'abord install_windows.bat.
  pause
  exit /b 1
)
.venv\Scripts\python.exe bot.py
pause
