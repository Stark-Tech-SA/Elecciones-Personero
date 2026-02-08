# Elecciones Personero

## Ejecutar en desarrollo (VS Code)
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

### Levantar servidores separados
En una terminal (Administración):
```bash
python run_admin.py
```
- URL: `http://localhost:5000/admin/login`
- Usuario por defecto: `admin`
- Clave por defecto: `admin123`

En otra terminal (Votación):
```bash
python run_voting.py
```
- URL: `http://localhost:5001/login`

## Generar `.exe` en Windows
Ejecuta en `cmd`:
```bat
build_exe.bat
```

El ejecutable queda en:
- `dist\EleccionesPersonero.exe`

> Nota: PyInstaller genera `.exe` cuando se ejecuta en Windows.
