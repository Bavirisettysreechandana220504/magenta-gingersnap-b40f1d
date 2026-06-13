from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import sqlite3
import os
import re
import cv2
import numpy as np
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
SCAN_FOLDER = "scan_uploads"
DB_FILE = "derm_assist.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SCAN_FOLDER, exist_ok=True)

def connect_db():
    return sqlite3.connect(DB_FILE)

def file_url(folder, filename):
    if not filename:
        return ""
    return request.host_url.rstrip("/") + f"/{folder}/{filename}"

def ensure_tables():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        age TEXT NOT NULL,
        gender TEXT NOT NULL,
        skin TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        image TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        concerns TEXT NOT NULL,
        result TEXT NOT NULL,
        acne_count INTEGER DEFAULT 0,
        severity TEXT,
        hydration TEXT,
        oil_level TEXT,
        sensitivity TEXT,
        glow_score TEXT,
        routine TEXT,
        doctor_advice TEXT,
        image TEXT,
        marked_image TEXT,
        date TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reset_tokens(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        token TEXT NOT NULL,
        created_at TEXT
    )
    """)

    def table_columns(table):
        cur.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}

    user_columns = table_columns("users")
    user_migrations = {
        "name": "TEXT DEFAULT ''",
        "mobile": "TEXT DEFAULT ''",
        "age": "TEXT DEFAULT ''",
        "gender": "TEXT DEFAULT ''",
        "skin": "TEXT DEFAULT ''",
        "email": "TEXT DEFAULT ''",
        "password": "TEXT DEFAULT ''",
        "image": "TEXT DEFAULT ''"
    }
    for column, definition in user_migrations.items():
        if column not in user_columns:
            cur.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

    scan_columns = table_columns("scans")
    scan_migrations = {
        "concerns": "TEXT DEFAULT ''",
        "acne_count": "INTEGER DEFAULT 0",
        "severity": "TEXT",
        "hydration": "TEXT",
        "oil_level": "TEXT",
        "sensitivity": "TEXT",
        "glow_score": "TEXT",
        "routine": "TEXT",
        "doctor_advice": "TEXT",
        "image": "TEXT",
        "marked_image": "TEXT",
        "date": "TEXT"
    }
    for column, definition in scan_migrations.items():
        if column not in scan_columns:
            cur.execute(f"ALTER TABLE scans ADD COLUMN {column} {definition}")

    scan_columns = table_columns("scans")
    if "concern" in scan_columns and "concerns" in scan_columns:
        cur.execute("UPDATE scans SET concerns=concern WHERE (concerns IS NULL OR concerns='') AND concern IS NOT NULL")

    conn.commit()
    conn.close()

ensure_tables()

@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})

@app.route("/")
def index():
    return send_from_directory(".", "splash.html")

@app.route("/<path:filename>")
def public_file(filename):
    allowed_ext = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".ico"}
    _, ext = os.path.splitext(filename)
    if ext.lower() in allowed_ext and os.path.exists(filename):
        return send_from_directory(".", filename)
    return jsonify({"status": "fail", "message": "Not found"}), 404

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/scan_uploads/<path:filename>")
def scan_file(filename):
    return send_from_directory(SCAN_FOLDER, filename)

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.form

        name = data.get("name", "").strip()
        mobile = data.get("mobile", "").strip()
        age = data.get("age", "").strip()
        gender = data.get("gender", "").strip()
        skin = data.get("skin", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        if not name or not mobile or not age or not gender or not skin or not email or not password:
            return jsonify({"status": "fail", "message": "Please fill all fields"})

        if not re.match(r'^[A-Za-z ]{2,50}$', name):
            return jsonify({"status": "fail", "message": "Name should contain only letters and spaces"})

        if not re.match(r'^\+91[6-9]\d{9}$', mobile):
            return jsonify({"status": "fail", "message": "Use +91XXXXXXXXXX format"})

        if not age.isdigit() or int(age) <= 0:
            return jsonify({"status": "fail", "message": "Please enter valid age"})

        if not re.match(r'^[A-Za-z0-9._%+-]+@gmail\.com$', email):
            return jsonify({"status": "fail", "message": "Use a valid Gmail address"})

        if not re.match(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&]).{6,}$', password):
            return jsonify({"status": "fail", "message": "Password must include uppercase, lowercase, number and special character"})

        image_file = request.files.get("image")
        if not image_file or not image_file.filename:
            return jsonify({"status": "fail", "message": "Please upload an image"})

        filename = datetime.now().strftime("%Y%m%d%H%M%S_") + secure_filename(image_file.filename)
        image_file.save(os.path.join(UPLOAD_FOLDER, filename))

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO users(name, mobile, age, gender, skin, email, password, image)
        VALUES(?,?,?,?,?,?,?,?)
        """, (name, mobile, age, gender, skin, email, password, filename))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Registration Successful"})

    except sqlite3.IntegrityError:
        return jsonify({"status": "fail", "message": "Email already exists"})
    except Exception as e:
        print("REGISTER ERROR:", e)
        return jsonify({"status": "fail", "message": "Server Error"})

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE email=? AND password=?", (email, password))
        user = cur.fetchone()
        conn.close()

        if user:
            return jsonify({
                "status": "success",
                "message": "Login Successful",
                "email": email,
                "name": user[0]
            })

        return jsonify({"status": "fail", "message": "Invalid Credentials"})

    except Exception as e:
        print("LOGIN ERROR:", e)
        return jsonify({"status": "fail", "message": "Server Error"})

@app.route("/forgot_password", methods=["POST"])
def forgot_password():
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip()

        if not email:
            return jsonify({"status": "fail", "message": "Email required"})

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        user = cur.fetchone()

        if not user:
            conn.close()
            return jsonify({"status": "fail", "message": "Email not found"})

        token = str(uuid.uuid4())[:8]
        cur.execute("INSERT INTO reset_tokens(email, token, created_at) VALUES(?,?,?)",
                    (email, token, datetime.now().strftime("%d-%m-%Y %I:%M %p")))
        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Reset token created for demo",
            "token": token
        })

    except Exception as e:
        print("FORGOT ERROR:", e)
        return jsonify({"status": "fail", "message": "Server Error"})

@app.route("/reset_password", methods=["POST"])
def reset_password():
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip()
        token = data.get("token", "").strip()
        new_password = data.get("new_password", "").strip()

        if not email or not token or not new_password:
            return jsonify({"status": "fail", "message": "All fields required"})

        if not re.match(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&]).{6,}$', new_password):
            return jsonify({"status": "fail", "message": "Weak password"})

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM reset_tokens WHERE email=? AND token=? ORDER BY id DESC LIMIT 1", (email, token))
        valid = cur.fetchone()

        if not valid:
            conn.close()
            return jsonify({"status": "fail", "message": "Invalid token"})

        cur.execute("UPDATE users SET password=? WHERE email=?", (new_password, email))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Password reset successful"})

    except Exception as e:
        print("RESET ERROR:", e)
        return jsonify({"status": "fail", "message": "Server Error"})

def analyze_image(image_path):
    img = cv2.imread(image_path)

    if img is None:
        return {
            "acne_count": 0,
            "severity": "Low",
            "hydration": "65%",
            "oil_level": "50%",
            "sensitivity": "45%",
            "glow_score": "65%",
            "marked_file": ""
        }

    img = cv2.resize(img, (600, 600))
    marked = img.copy()

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 45, 50])
    upper_red1 = np.array([15, 255, 255])
    lower_red2 = np.array([160, 45, 50])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    acne_mask = mask1 + mask2

    kernel = np.ones((4, 4), np.uint8)
    acne_mask = cv2.morphologyEx(acne_mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(acne_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    acne_count = 0
    for c in contours:
        area = cv2.contourArea(c)
        if 18 < area < 900:
            acne_count += 1
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(marked, (x, y), (x + w, y + h), (255, 0, 140), 3)
            cv2.putText(marked, "spot", (x, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 140), 1)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    saturation = np.mean(hsv[:, :, 1])

    if acne_count <= 5:
        severity = "Low"
    elif acne_count <= 15:
        severity = "Medium"
    else:
        severity = "High"

    hydration_value = max(35, min(85, int(100 - saturation / 3)))
    oil_value = max(30, min(90, int(saturation / 2 + acne_count * 2)))
    glow_value = max(30, min(90, int(brightness / 2)))
    sensitivity_value = max(25, min(90, int(acne_count * 3 + saturation / 4)))

    base, ext = os.path.splitext(os.path.basename(image_path))
    marked_file = base + "_marked" + ext
    marked_path = os.path.join(SCAN_FOLDER, marked_file)
    cv2.imwrite(marked_path, marked)

    return {
        "acne_count": acne_count,
        "severity": severity,
        "hydration": f"{hydration_value}%",
        "oil_level": f"{oil_value}%",
        "sensitivity": f"{sensitivity_value}%",
        "glow_score": f"{glow_value}%",
        "marked_file": marked_file
    }

def make_routine(concerns, severity):
    selected = concerns.lower()

    routine = []

    routine.append("Morning: Use a gentle cleanser according to your skin type.")
    routine.append("Morning: Apply lightweight moisturizer.")
    routine.append("Morning: Apply SPF 50 sunscreen daily.")

    if "acne" in selected:
        routine.append("Night: Use salicylic acid serum 2-3 times weekly.")
        routine.append("Avoid harsh scrubs and comedogenic products.")

    if "dark spots" in selected or "pigmentation" in selected:
        routine.append("Morning: Use vitamin C serum before sunscreen.")
        routine.append("Night: Use niacinamide or alpha arbutin for uneven tone.")

    if "dryness" in selected:
        routine.append("Use hyaluronic acid serum on damp skin.")
        routine.append("Use ceramide moisturizer at night.")

    if "oily skin" in selected:
        routine.append("Use gel moisturizer and matte sunscreen.")
        routine.append("Use niacinamide serum for oil control.")

    if "sensitivity" in selected or "redness" in selected:
        routine.append("Use fragrance-free cleanser and calming moisturizer.")
        routine.append("Avoid strong exfoliation and patch test products.")

    if "dullness" in selected:
        routine.append("Use mild exfoliation once weekly and glow serum.")

    if severity == "High":
        routine.append("Because severity is high, consult a dermatologist before using strong actives.")

    return " | ".join(routine)

def doctor_advice(severity):
    if severity == "High":
        return "Severe concern detected. Suggested: consult a dermatologist. Indian options: Apollo Dermatology, Kaya Skin Clinic, Oliva Skin & Hair Clinic, Manipal Hospital Dermatology, Practo dermatologist consultation."
    if severity == "Medium":
        return "Moderate concern detected. If it continues for more than 2-3 weeks, consult a dermatologist."
    return "Mild concern detected. Home skincare routine may help, but consult a doctor if irritation increases."

@app.route("/scan_ai", methods=["POST"])
def scan_ai():
    try:
        email = request.form.get("email", "guest@dermassist.com").strip()
        concerns = request.form.get("concerns", "").strip()
        image_file = request.files.get("image")

        if not concerns:
            return jsonify({"status": "fail", "message": "Select at least one concern"})

        if not image_file or not image_file.filename:
            return jsonify({"status": "fail", "message": "Image required"})

        filename = datetime.now().strftime("%Y%m%d%H%M%S_") + secure_filename(image_file.filename)
        image_path = os.path.join(SCAN_FOLDER, filename)
        image_file.save(image_path)

        ai = analyze_image(image_path)
        routine = make_routine(concerns, ai["severity"])
        doctor = doctor_advice(ai["severity"])

        result = (
            f"AI analysis completed for: {concerns}. "
            f"Acne/spot count: {ai['acne_count']}. "
            f"Severity: {ai['severity']}. "
            f"Hydration: {ai['hydration']}. Oil level: {ai['oil_level']}. "
            f"Sensitivity: {ai['sensitivity']}. Glow score: {ai['glow_score']}."
        )

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(scans)")
        scan_columns = {row[1] for row in cur.fetchall()}
        insert_data = {
            "email": email,
            "concerns": concerns,
            "result": result,
            "acne_count": ai["acne_count"],
            "severity": ai["severity"],
            "hydration": ai["hydration"],
            "oil_level": ai["oil_level"],
            "sensitivity": ai["sensitivity"],
            "glow_score": ai["glow_score"],
            "routine": routine,
            "doctor_advice": doctor,
            "image": filename,
            "marked_image": ai["marked_file"],
            "date": datetime.now().strftime("%d-%m-%Y %I:%M %p")
        }
        if "concern" in scan_columns:
            insert_data["concern"] = concerns
        columns = [column for column in insert_data if column in scan_columns]
        placeholders = ",".join("?" for _ in columns)
        cur.execute(
            f"INSERT INTO scans({','.join(columns)}) VALUES({placeholders})",
            tuple(insert_data[column] for column in columns)
        )
        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "AI scan completed",
            "concerns": concerns,
            "result": result,
            "acne_count": ai["acne_count"],
            "severity": ai["severity"],
            "hydration": ai["hydration"],
            "oil_level": ai["oil_level"],
            "sensitivity": ai["sensitivity"],
            "glow_score": ai["glow_score"],
            "routine": routine,
            "doctor_advice": doctor,
            "image_url": file_url("scan_uploads", filename),
            "marked_image_url": file_url("scan_uploads", ai["marked_file"])
        })

    except Exception as e:
        print("SCAN AI ERROR:", e)
        return jsonify({"status": "fail", "message": "Server Error"})

@app.route("/scan_history", methods=["GET"])
def scan_history():
    try:
        email = request.args.get("email", "guest@dermassist.com").strip()

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
        SELECT concerns,result,acne_count,severity,hydration,oil_level,sensitivity,glow_score,
        routine,doctor_advice,image,marked_image,date
        FROM scans
        WHERE email=?
        ORDER BY id DESC
        """, (email,))
        rows = cur.fetchall()
        conn.close()

        history = []
        for r in rows:
            history.append({
                "concerns": r[0],
                "result": r[1],
                "acne_count": r[2],
                "severity": r[3],
                "hydration": r[4],
                "oil_level": r[5],
                "sensitivity": r[6],
                "glow_score": r[7],
                "routine": r[8],
                "doctor_advice": r[9],
                "image_url": file_url("scan_uploads", r[10]),
                "marked_image_url": file_url("scan_uploads", r[11]),
                "date": r[12]
            })

        return jsonify({"status": "success", "history": history})

    except Exception as e:
        print("HISTORY ERROR:", e)
        return jsonify({"status": "fail", "message": "Server Error"})

@app.route("/profile", methods=["GET"])
def profile():
    try:
        email = request.args.get("email", "").strip()
        if not email:
            return jsonify({"status": "fail", "message": "Email required"})

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT name, mobile, age, gender, skin, email, image FROM users WHERE email=?", (email,))
        user = cur.fetchone()
        conn.close()

        if not user:
            return jsonify({"status": "fail", "message": "User not found"})

        return jsonify({
            "status": "success",
            "user": {
                "name": user[0],
                "mobile": user[1],
                "age": user[2],
                "gender": user[3],
                "skin": user[4],
                "email": user[5],
                "image_url": file_url("uploads", user[6])
            }
        })

    except Exception as e:
        print("PROFILE ERROR:", e)
        return jsonify({"status": "fail", "message": "Server Error"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
