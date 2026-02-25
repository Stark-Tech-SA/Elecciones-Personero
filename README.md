# Elecciones Personero

## Ejecutar en desarrollo (VS Code)
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
python run_admin.py
```

## Rutas principales (mismo host)
- Administración: `http://localhost:5000/admin/login`
- Votación estudiantes: `http://localhost:5000/votacion/login`

## Generar `.exe` en Windows
Ejecuta en `cmd`:
```bat
build_exe.bat
```

El ejecutable queda en:
- `dist\EleccionesPersonero.exe`

> Nota: PyInstaller genera `.exe` cuando se ejecuta en Windows.


## Jurado de votación
- Login jurado: `http://localhost:5000/jurado/login`
- Usuario inicial: `jurado`
- Clave inicial: `jurado123`
> Recomendado cambiar credenciales en base de datos tras la primera ejecución.


## Inicio rápido en Windows (.bat)
En `cmd` puedes preparar e iniciar la app con un solo archivo:
```bat
iniciar_app.bat
```
Este script crea `.venv` (si no existe), instala dependencias y ejecuta `run_admin.py`.
