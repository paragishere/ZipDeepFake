from flask import Blueprint, render_template, request, session, redirect
import os
import hashlib
import random
import bcrypt

from flask_mail import Message
from flask_dance.contrib.google import google

from app import mail
from .db import get_db
from .utils import predict_video, log_event

main = Blueprint('main', __name__)


# ==================================================
# HOME (PUBLIC PAGE NOW)
# ==================================================
@main.route('/')
def home():

    return render_template(
        "index.html",
        logged_in=('user' in session)
    )


# ==================================================
# UPLOAD VIDEO (LOGIN REQUIRED)
# ==================================================
@main.route('/upload', methods=['POST'])
def upload():

    if 'user' not in session:
        return redirect('/login')

    log_event("UPLOAD_START")

    if 'video' not in request.files:
        log_event("UPLOAD_FAIL", "NO_FILE")
        return "No file uploaded"

    file = request.files['video']

    if file.filename == "":
        log_event("UPLOAD_FAIL", "EMPTY_FILE")
        return "No file selected"

    if not file.filename.endswith(('.mp4', '.avi', '.mov')):
        log_event("UPLOAD_FAIL", "INVALID_TYPE")
        return "Invalid file type"

    try:
        filepath = os.path.join("uploads", file.filename)
        file.save(filepath)

        log_event("FILE_SAVED")

        data = predict_video(filepath)

        if isinstance(data, str):
            return render_template(
                "result.html",
                result=data,
                score="--",
                avg_score="--",
                fake_ratio="--",
                variance="--"
            )

        result = data["result"]

        if result == "FAKE":
            log_event("SUSPICIOUS_UPLOAD", "FAKE_DETECTED")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO logs
            (email, filename, result, ip, user_agent)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session.get("user"),
            file.filename,
            result,
            request.remote_addr,
            request.headers.get("User-Agent")
        ))

        conn.commit()
        conn.close()

        log_event("UPLOAD_SUCCESS")

        return render_template(
            "result.html",
            result=result,
            score=data["score"],
            avg_score=data["avg_score"],
            fake_ratio=data["fake_ratio"],
            variance=data["variance"]
        )

    except Exception as e:
        log_event("UPLOAD_ERROR", str(e))
        return str(e)


# ==================================================
# LOGIN
# ==================================================
@main.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        if user and user['password'] and bcrypt.checkpw(
            password.encode(),
            user['password']
        ):

            if user['is_verified'] == 0:
                conn.close()
                return "Verify email first"

            cursor.execute("""
                UPDATE users
                SET ip=?, user_agent=?
                WHERE email=?
            """, (
                request.remote_addr,
                request.headers.get("User-Agent"),
                email
            ))

            conn.commit()
            conn.close()

            session['user'] = email
            log_event("LOGIN_SUCCESS")

            return redirect('/')

        conn.close()
        log_event("LOGIN_FAIL")
        return "Invalid login"

    return render_template("login.html")


# ==================================================
# REGISTER
# ==================================================
@main.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        otp = str(random.randint(100000, 999999))

        hashed = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt()
        )

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users
                (email, password, otp, is_verified)
                VALUES (?, ?, ?, 0)
            """, (
                email,
                hashed,
                otp
            ))

            conn.commit()

            msg = Message(
                "Verify Account",
                sender=os.getenv("MAIL_EMAIL"),
                recipients=[email]
            )

            msg.body = f"Your OTP is {otp}"
            mail.send(msg)

            conn.close()

            return redirect(f"/verify?email={email}")

        except:
            conn.close()
            return "User already exists"

    return render_template("register.html")


# ==================================================
# VERIFY OTP
# ==================================================
@main.route('/verify', methods=['GET', 'POST'])
def verify():

    email = request.args.get("email")

    if request.method == 'POST':

        otp = request.form['otp']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT otp FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        if user and user['otp'] == otp:

            cursor.execute("""
                UPDATE users
                SET is_verified=1, otp=NULL
                WHERE email=?
            """, (email,))

            conn.commit()
            conn.close()

            return redirect('/login')

        conn.close()
        return "Invalid OTP"

    return render_template(
        "verify.html",
        email=email
    )


# ==================================================
# GOOGLE LOGIN
# ==================================================
@main.route('/google_login')
def google_login():

    if not google.authorized:
        return redirect('/login/google')

    resp = google.get("/oauth2/v2/userinfo")

    if not resp.ok:
        return "Google auth failed"

    info = resp.json()
    email = info.get("email")

    if not email:
        return "Email unavailable"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    )

    user = cursor.fetchone()

    if not user:
        cursor.execute("""
            INSERT INTO users
            (email, password, is_verified, ip, user_agent)
            VALUES (?, ?, 1, ?, ?)
        """, (
            email,
            None,
            request.remote_addr,
            request.headers.get("User-Agent")
        ))

    else:
        cursor.execute("""
            UPDATE users
            SET ip=?, user_agent=?
            WHERE email=?
        """, (
            request.remote_addr,
            request.headers.get("User-Agent"),
            email
        ))

    conn.commit()
    conn.close()

    session['user'] = email
    log_event("GOOGLE_LOGIN")

    return redirect('/')


# ==================================================
# PROFILE
# ==================================================
@main.route('/profile')
def profile():

    if 'user' not in session:
        return redirect('/login')

    email = session['user']

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    )
    user = cursor.fetchone()

    cursor.execute("""
        SELECT filename, result, uploaded_at
        FROM logs
        WHERE email=?
        ORDER BY uploaded_at DESC
        LIMIT 20
    """, (email,))

    scans = cursor.fetchall()

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        scans=scans
    )


# ==================================================
# USER LOGOUT
# ==================================================
@main.route('/logout')
def logout():

    session.pop('user', None)
    log_event("USER_LOGOUT")

    return redirect('/')


# ==================================================
# ADMIN LOGIN
# ==================================================
@main.route('/admin/login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        hashed = hashlib.sha256(
            password.encode()
        ).hexdigest()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM admin
            WHERE username=? AND password=?
        """, (
            username,
            hashed
        ))

        admin = cursor.fetchone()

        conn.close()

        if admin:
            session['admin'] = username
            return redirect('/admin')

        return "Invalid credentials"

    return render_template("admin_login.html")


# ==================================================
# ADMIN PANEL
# ==================================================
@main.route('/admin')
def admin():

    if 'admin' not in session:
        return redirect('/admin/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM logs
        ORDER BY uploaded_at DESC
    """)

    logs = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        logs=logs
    )


# ==================================================
# EVENTS
# ==================================================
@main.route('/events')
def events():

    if 'admin' not in session:
        return redirect('/admin/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM events
        ORDER BY timestamp DESC
        LIMIT 100
    """)

    data = cursor.fetchall()

    conn.close()

    return render_template(
        "events.html",
        data=data
    )


# ==================================================
# ADMIN LOGOUT
# ==================================================
@main.route('/admin/logout')
def admin_logout():

    session.pop('admin', None)

    return redirect('/admin/login')