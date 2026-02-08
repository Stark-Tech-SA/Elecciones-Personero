# Sistema de Elecciones - Personero y Contralor

Aplicación web en Flask para administrar elecciones estudiantiles de **Personero** y **Contralor** (incluyendo registro de suplentes).

## Funcionalidades

- Sección de información del colegio (nombre, ciudad, año, descripción y logo).
- Registro de candidatos con foto y cargo.
- Carga masiva de estudiantes aptos desde **Excel (.xlsx)** o **CSV**.
- Generación automática de:
  - Usuario único por estudiante.
  - Token único para QR.
  - Certificado/credencial imprimible por estudiante.
- Inicio de sesión por usuario único para votar.
- Bloqueo de doble votación (si intenta entrar de nuevo, aparece aviso de "ya votó").
- Escrutinio y estadísticas de participación.

## Estructura esperada para archivo de estudiantes

Columnas obligatorias:

- `doc_id`
- `full_name`
- `grade`
- `group_name`

## Ejecución local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abrir `http://localhost:5000`.

## Flujo recomendado

1. Ir a `/admin`.
2. Cargar información del colegio.
3. Registrar candidatos.
4. Importar estudiantes.
5. Imprimir certificados individuales con QR.
6. Estudiantes votan en `/login` usando usuario único.
7. Revisar resultados en `/admin/results`.
