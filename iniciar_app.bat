@echo off
setlocal

REM Script rápido para Windows: crea/activa venv, instala dependencias y levanta la app
cd /d %~dp0

if not exist .venv (
  echo [1/4] Creando entorno virtual...
  py -m venv .venv
)

echo [2/4] Activando entorno virtual...
call .venv\Scripts\activate

echo [3/4] Actualizando pip e instalando dependencias...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [4/4] Iniciando servidor Flask (admin + votacion en mismo host)...
python run_admin.py

endlocal
