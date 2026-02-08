@echo off
setlocal

py -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconfirm --clean --onefile --name EleccionesPersonero app.py

echo.
echo EXE generado en dist\EleccionesPersonero.exe
endlocal
