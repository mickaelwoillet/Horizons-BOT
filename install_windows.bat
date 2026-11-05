@echo off
setlocal
chcp 65001 >nul

echo Verification de Python...
python --version
if errorlevel 1 (
    echo ERREUR : Python est introuvable. Installe Python 3.11, 3.12 ou 3.13 et coche "Add Python to PATH".
    pause
    exit /b 1
)

echo.
echo Creation de l'environnement virtuel...
python -m venv .venv
if errorlevel 1 (
    echo ERREUR : impossible de creer l'environnement virtuel.
    pause
    exit /b 1
)

echo.
echo Installation des dependances...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo ERREUR pendant la mise a jour de pip.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR pendant l'installation des dependances.
    pause
    exit /b 1
)

if not exist .env (
    copy .env.example .env
    echo Fichier .env cree depuis .env.example.
)

echo.
echo Installation terminee. Verifie le fichier .env puis lance start_windows.bat.
pause
endlocal
