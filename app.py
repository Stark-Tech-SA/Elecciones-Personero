import io
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import qrcode
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
UPLOADS = BASE_DIR / "uploads"
UPLOADS.mkdir(exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ADMIN_PORT = 5000
VOTING_PORT = 5001

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS school_info (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            school_name TEXT,
            city TEXT,
            election_year TEXT,
            logo_path TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS design_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            page_title TEXT DEFAULT 'Elecciones Personero',
            header_color TEXT DEFAULT '#0d6efd',
            background_color TEXT DEFAULT '#f8f9fa',
            text_color TEXT DEFAULT '#212529'
        );

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            grade TEXT,
            position TEXT NOT NULL,
            proposal TEXT,
            photo_path TEXT
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT,
            full_name TEXT NOT NULL,
            grade TEXT,
            group_name TEXT,
            unique_user TEXT UNIQUE NOT NULL,
            qr_token TEXT UNIQUE NOT NULL,
            voted INTEGER DEFAULT 0,
            voted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            position TEXT NOT NULL,
            candidate_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        );
        """
    )
    db.execute(
        """
        INSERT INTO design_settings (id)
        VALUES (1)
        ON CONFLICT(id) DO NOTHING
        """
    )
    db.execute(
        """
        INSERT INTO admin_users (username, password)
        VALUES ('admin', 'admin123')
        ON CONFLICT(username) DO NOTHING
        """
    )
    db.commit()
    db.close()


init_db()


def app_base_url(port: int) -> str:
    return f"http://localhost:{port}"


def request_port() -> int | None:
    host = request.host or ""
    if ":" not in host:
        return None
    try:
        return int(host.rsplit(":", 1)[1])
    except ValueError:
        return None


def get_design_settings():
    db = get_db()
    row = db.execute("SELECT * FROM design_settings WHERE id=1").fetchone()
    return row


@app.context_processor
def inject_theme_context():
    return {
        "theme": get_design_settings(),
        "ADMIN_BASE": app_base_url(ADMIN_PORT),
        "VOTING_BASE": app_base_url(VOTING_PORT),
    }


def allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_upload(file_storage, prefix: str) -> str | None:
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_image(file_storage.filename):
        return None
    filename = secure_filename(file_storage.filename)
    out_name = f"{prefix}_{secrets.token_hex(8)}_{filename}"
    destination = UPLOADS / out_name
    file_storage.save(destination)
    return f"uploads/{out_name}"


def generate_unique_user() -> str:
    # Usuario numérico corto (máximo 8 dígitos)
    return f"{secrets.randbelow(10**8):08d}"


def generate_unique_user_non_colliding(db):
    for _ in range(20):
        candidate = generate_unique_user()
        exists = db.execute("SELECT id FROM students WHERE unique_user = ?", (candidate,)).fetchone()
        if not exists:
            return candidate
    raise RuntimeError("No fue posible generar usuario único")


def admin_required():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))
    return None


@app.before_request
def split_by_port():
    port = request_port()
    path = request.path

    if path.startswith("/uploads") or path.startswith("/static"):
        return None

    if path == "/":
        if port == VOTING_PORT:
            return redirect(url_for("login"))
        return redirect(url_for("admin_login"))

    if port == VOTING_PORT and path.startswith("/admin"):
        return redirect(f"{app_base_url(ADMIN_PORT)}/admin/login")

    if port == ADMIN_PORT and (
        path.startswith("/login")
        or path.startswith("/vote")
        or path.startswith("/logout")
        or path.startswith("/qr")
    ):
        return redirect(f"{app_base_url(VOTING_PORT)}{path}")

    return None


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOADS, filename)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        db = get_db()
        admin = db.execute(
            "SELECT * FROM admin_users WHERE username = ? AND password = ?", (username, password)
        ).fetchone()
        if not admin:
            flash("Credenciales de administrador inválidas.")
            return redirect(url_for("admin_login"))
        session["admin_logged"] = True
        session["admin_username"] = admin["username"]
        return redirect(url_for("admin_home"))

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin_home():
    guard = admin_required()
    if guard:
        return guard

    db = get_db()
    school = db.execute("SELECT * FROM school_info WHERE id=1").fetchone()
    counts = {
        "candidates": db.execute("SELECT COUNT(*) AS c FROM candidates").fetchone()["c"],
        "students": db.execute("SELECT COUNT(*) AS c FROM students").fetchone()["c"],
        "voted": db.execute("SELECT COUNT(*) AS c FROM students WHERE voted=1").fetchone()["c"],
    }
    return render_template("admin_home.html", school=school, counts=counts)


@app.route("/admin/design", methods=["GET", "POST"])
def design_settings():
    guard = admin_required()
    if guard:
        return guard

    db = get_db()
    if request.method == "POST":
        db.execute(
            """
            UPDATE design_settings
            SET page_title = ?, header_color = ?, background_color = ?, text_color = ?
            WHERE id = 1
            """,
            (
                request.form.get("page_title", "Elecciones Personero").strip() or "Elecciones Personero",
                request.form.get("header_color", "#0d6efd").strip() or "#0d6efd",
                request.form.get("background_color", "#f8f9fa").strip() or "#f8f9fa",
                request.form.get("text_color", "#212529").strip() or "#212529",
            ),
        )
        db.commit()
        flash("Diseño actualizado correctamente.")
        return redirect(url_for("design_settings"))

    settings = db.execute("SELECT * FROM design_settings WHERE id=1").fetchone()
    return render_template("design_settings.html", settings=settings)


@app.route("/admin/school", methods=["GET", "POST"])
def school_info():
    guard = admin_required()
    if guard:
        return guard

    db = get_db()
    if request.method == "POST":
        logo_path = save_upload(request.files.get("logo"), "logo")
        current = db.execute("SELECT * FROM school_info WHERE id=1").fetchone()
        final_logo = logo_path or (current["logo_path"] if current else None)

        db.execute(
            """
            INSERT INTO school_info (id, school_name, city, election_year, logo_path, description)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                school_name=excluded.school_name,
                city=excluded.city,
                election_year=excluded.election_year,
                logo_path=excluded.logo_path,
                description=excluded.description
            """,
            (
                request.form.get("school_name", "").strip(),
                request.form.get("city", "").strip(),
                request.form.get("election_year", "").strip(),
                final_logo,
                request.form.get("description", "").strip(),
            ),
        )
        db.commit()
        flash("Información del colegio guardada correctamente.")
        return redirect(url_for("school_info"))

    school = db.execute("SELECT * FROM school_info WHERE id=1").fetchone()
    return render_template("school_info.html", school=school)


@app.route("/admin/candidates", methods=["GET", "POST"])
def candidates():
    guard = admin_required()
    if guard:
        return guard

    db = get_db()
    if request.method == "POST":
        photo_path = save_upload(request.files.get("photo"), "candidate")
        db.execute(
            """
            INSERT INTO candidates (full_name, grade, position, proposal, photo_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request.form.get("full_name", "").strip(),
                request.form.get("grade", "").strip(),
                request.form.get("position", "").strip(),
                request.form.get("proposal", "").strip(),
                photo_path,
            ),
        )
        db.commit()
        flash("Candidato registrado.")
        return redirect(url_for("candidates"))

    all_candidates = db.execute("SELECT * FROM candidates ORDER BY position, full_name").fetchall()
    return render_template("candidates.html", candidates=all_candidates)


@app.route("/admin/students", methods=["GET", "POST"])
def students_upload():
    guard = admin_required()
    if guard:
        return guard

    db = get_db()
    if request.method == "POST":
        file = request.files.get("students_file")
        if not file or file.filename == "":
            flash("Debes seleccionar un archivo Excel o CSV.")
            return redirect(url_for("students_upload"))

        filename = file.filename.lower()
        if filename.endswith(".xlsx"):
            df = pd.read_excel(file)
        elif filename.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            flash("Formato no soportado. Usa .xlsx o .csv")
            return redirect(url_for("students_upload"))

        required_columns = ["doc_id", "full_name", "grade", "group_name"]
        if not set(required_columns).issubset(df.columns):
            flash("El archivo debe tener columnas: doc_id, full_name, grade, group_name")
            return redirect(url_for("students_upload"))

        inserted = 0
        skipped = 0

        for _, row in df.iterrows():
            full_name = str(row.get("full_name", "")).strip()
            if not full_name:
                skipped += 1
                continue

            doc_id = str(row.get("doc_id", "")).strip()
            exists = db.execute(
                "SELECT id FROM students WHERE doc_id = ? AND doc_id <> ''", (doc_id,)
            ).fetchone()
            if exists:
                skipped += 1
                continue

            unique_user = generate_unique_user_non_colliding(db)
            qr_token = secrets.token_urlsafe(16)
            db.execute(
                """
                INSERT INTO students (doc_id, full_name, grade, group_name, unique_user, qr_token)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    full_name,
                    str(row.get("grade", "")).strip(),
                    str(row.get("group_name", "")).strip(),
                    unique_user,
                    qr_token,
                ),
            )
            inserted += 1

        db.commit()
        flash(f"Carga completada: {inserted} estudiantes nuevos, {skipped} omitidos.")
        return redirect(url_for("students_upload"))

    students = db.execute("SELECT * FROM students ORDER BY full_name").fetchall()
    return render_template("students_upload.html", students=students)


def build_certificate_pdf(students, school):
    packet = io.BytesIO()
    pdf = canvas.Canvas(packet, pagesize=A4)
    page_w, page_h = A4

    margin = 24
    cols = 2
    rows = 2
    cert_w = (page_w - margin * 2 - 12) / cols
    cert_h = (page_h - margin * 2 - 12) / rows

    logo_reader = None
    if school and school["logo_path"]:
        logo_file = BASE_DIR / school["logo_path"]
        if logo_file.exists():
            logo_reader = ImageReader(str(logo_file))

    for idx, student in enumerate(students):
        slot = idx % 4
        col = slot % 2
        row = slot // 2

        x = margin + col * (cert_w + 12)
        y = page_h - margin - (row + 1) * cert_h - row * 12

        pdf.roundRect(x, y, cert_w, cert_h, 8)
        pdf.setFont("Helvetica-Bold", 11)
        school_name = school["school_name"] if school and school["school_name"] else "Institución educativa"
        pdf.drawString(x + 10, y + cert_h - 18, school_name)

        if logo_reader:
            pdf.drawImage(logo_reader, x + cert_w - 54, y + cert_h - 54, width=42, height=42, preserveAspectRatio=True)

        pdf.setFont("Helvetica", 9)
        pdf.drawString(x + 10, y + cert_h - 36, "Certificado de participación electoral")
        pdf.drawString(x + 10, y + cert_h - 52, f"Estudiante: {student['full_name']}")
        pdf.drawString(x + 10, y + cert_h - 66, f"Documento: {student['doc_id'] or '-'}")
        pdf.drawString(x + 10, y + cert_h - 80, f"Usuario: {student['unique_user']}")
        status_txt = "Votó" if student["voted"] else "Pendiente por votar"
        pdf.drawString(x + 10, y + cert_h - 94, f"Estado: {status_txt}")

        vote_url = f"{app_base_url(VOTING_PORT)}/vote/access/{student['qr_token']}"
        qr_img = qrcode.make(vote_url)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        pdf.drawImage(ImageReader(qr_buf), x + 10, y + 10, width=70, height=70)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x + 86, y + 22, "Escanea para ingresar")
        pdf.drawString(x + 86, y + 12, "a la votación")

        if slot == 3 and idx != len(students) - 1:
            pdf.showPage()

    pdf.save()
    packet.seek(0)
    return packet


@app.route("/admin/certificates/pdf")
def certificates_pdf():
    guard = admin_required()
    if guard:
        return guard

    db = get_db()
    students = db.execute("SELECT * FROM students ORDER BY full_name").fetchall()
    school = db.execute("SELECT * FROM school_info WHERE id = 1").fetchone()
    if not students:
        flash("No hay estudiantes para generar certificados.")
        return redirect(url_for("students_upload"))

    pdf_bytes = build_certificate_pdf(students, school)
    return send_file(
        pdf_bytes,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="certificados_estudiantes.pdf",
    )


@app.route("/admin/results")
def results():
    guard = admin_required()
    if guard:
        return guard

    db = get_db()
    total_students = db.execute("SELECT COUNT(*) AS c FROM students").fetchone()["c"]
    total_voted = db.execute("SELECT COUNT(*) AS c FROM students WHERE voted=1").fetchone()["c"]

    tally = db.execute(
        """
        SELECT v.position, c.full_name, COUNT(v.id) AS votes
        FROM votes v
        JOIN candidates c ON c.id = v.candidate_id
        GROUP BY v.position, c.full_name
        ORDER BY v.position, votes DESC
        """
    ).fetchall()

    turnout = round((total_voted / total_students) * 100, 2) if total_students else 0

    return render_template(
        "results.html",
        tally=tally,
        total_students=total_students,
        total_voted=total_voted,
        turnout=turnout,
    )


@app.route("/vote/access/<token>")
def access_by_qr(token: str):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE qr_token = ?", (token,)).fetchone()
    if not student:
        flash("QR inválido.", "error")
        return redirect(url_for("login"))

    if student["voted"]:
        flash("Este usuario ya votó.", "already_voted")
        return redirect(url_for("login"))

    session["student_id"] = student["id"]
    return redirect(url_for("vote"))


@app.route("/qr/<token>")
def qr_image(token: str):
    vote_url = f"{app_base_url(VOTING_PORT)}/vote/access/{token}"
    img = qrcode.make(vote_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        unique_user = request.form.get("unique_user", "").strip()
        db = get_db()
        student = db.execute(
            "SELECT * FROM students WHERE unique_user = ?", (unique_user,)
        ).fetchone()

        if not student:
            flash("Usuario no válido.", "error")
            return redirect(url_for("login"))
        if student["voted"]:
            flash("Este usuario ya votó.", "already_voted")
            return redirect(url_for("login"))

        session["student_id"] = student["id"]
        return redirect(url_for("vote"))

    return render_template("login.html")


@app.route("/vote", methods=["GET", "POST"])
def vote():
    student_id = session.get("student_id")
    if not student_id:
        return redirect(url_for("login"))

    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student or student["voted"]:
        session.clear()
        flash("Este usuario ya votó o no existe.", "already_voted")
        return redirect(url_for("login"))

    positions = ["Personero", "Contralor"]
    candidates_by_position = {
        position: db.execute(
            "SELECT * FROM candidates WHERE position = ? ORDER BY full_name", (position,)
        ).fetchall()
        for position in positions
    }

    if request.method == "POST":
        personero_id = request.form.get("personero")
        contralor_id = request.form.get("contralor")

        if not personero_id or not contralor_id:
            flash("Debes seleccionar Personero y Contralor.", "error")
            return redirect(url_for("vote"))

        now = datetime.now().isoformat()
        db.execute(
            "INSERT INTO votes (student_id, position, candidate_id, created_at) VALUES (?, ?, ?, ?)",
            (student_id, "Personero", int(personero_id), now),
        )
        db.execute(
            "INSERT INTO votes (student_id, position, candidate_id, created_at) VALUES (?, ?, ?, ?)",
            (student_id, "Contralor", int(contralor_id), now),
        )
        db.execute(
            "UPDATE students SET voted = 1, voted_at = ? WHERE id = ?", (now, student_id)
        )
        db.commit()

        session.clear()
        flash("Voto registrado exitosamente.")
        return redirect(url_for("login"))

    return render_template("vote.html", student=student, candidates_by_position=candidates_by_position)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    # Ejecuta por defecto el servidor administrativo
    app.run(debug=True, host="0.0.0.0", port=ADMIN_PORT)
