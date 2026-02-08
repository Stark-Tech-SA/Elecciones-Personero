# Elecciones Personero

## Ejecutar en desarrollo
```bash
python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Generar `.exe` en Windows
Ejecuta en `cmd`:
```bat
build_exe.bat
```

El ejecutable queda en:
- `dist\\EleccionesPersonero.exe`

> Nota: PyInstaller genera `.exe` cuando se ejecuta en Windows.
