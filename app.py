import json
import os
import random
import smtplib
import threading
import time
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_mysqldb import MySQL
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    from groq import Groq
except ImportError:
    Groq = None


def load_env_file():
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
app.config["MYSQL_HOST"] = os.environ.get("SCHEDTALK_DB_HOST", "localhost")
app.config["MYSQL_PORT"] = int(os.environ.get("SCHEDTALK_DB_PORT", "3306"))
app.config["MYSQL_USER"] = os.environ.get("SCHEDTALK_DB_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("SCHEDTALK_DB_PASSWORD", "")
app.config["MYSQL_DB"] = os.environ.get("SCHEDTALK_DB_NAME", "schedtalk_db")
mysql_ssl_mode = os.environ.get("SCHEDTALK_DB_SSL_MODE", "").strip()
mysql_connect_timeout = os.environ.get("SCHEDTALK_DB_CONNECT_TIMEOUT", "").strip()
mysql_custom_options = {}
if mysql_ssl_mode:
    mysql_custom_options["ssl_mode"] = mysql_ssl_mode
if mysql_connect_timeout:
    mysql_custom_options["connect_timeout"] = int(mysql_connect_timeout)
if mysql_custom_options:
    app.config["MYSQL_CUSTOM_OPTIONS"] = mysql_custom_options
app.config["MAIL_SERVER"] = os.environ.get("SCHEDTALK_MAIL_SERVER", os.environ.get("MAIL_SERVER", "smtp.gmail.com"))
app.config["MAIL_PORT"] = int(os.environ.get("SCHEDTALK_MAIL_PORT", os.environ.get("MAIL_PORT", "465")))
app.config["MAIL_USE_SSL"] = os.environ.get("SCHEDTALK_MAIL_USE_SSL", os.environ.get("MAIL_USE_SSL", "1")) == "1"
app.config["MAIL_USERNAME"] = os.environ.get(
    "SCHEDTALK_MAIL_USERNAME", os.environ.get("MAIL_USERNAME", "sched.talk23@gmail.com")
)
app.config["MAIL_PASSWORD"] = os.environ.get("SCHEDTALK_MAIL_PASSWORD", os.environ.get("MAIL_PASSWORD", ""))
app.config["MAIL_TIMEOUT_SECONDS"] = int(os.environ.get("SCHEDTALK_MAIL_TIMEOUT_SECONDS", "8"))
app.config["CONTACT_RECIPIENT"] = os.environ.get("SCHEDTALK_CONTACT_RECIPIENT", "sched.talk23@gmail.com")
app.config["RESEND_API_KEY"] = os.environ.get("RESEND_API_KEY", "")
app.config["OTP_FROM_EMAIL"] = os.environ.get("OTP_FROM_EMAIL", "onboarding@resend.dev")
app.config["OTP_EXPIRE_SECONDS"] = int(os.environ.get("OTP_EXPIRE_SECONDS", "300"))
app.config["GROQ_API_KEY"] = os.environ.get("GROQ_API_KEY", "")
app.config["GROQ_MODEL"] = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")
app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "")
app.config["GOOGLE_REDIRECT_URI"] = os.environ.get("GOOGLE_REDIRECT_URI", "")

mysql = MySQL(app)
app.secret_key = os.environ.get("SCHEDTALK_SECRET_KEY", "schedtalk_secret_key")
RUN_SCHEMA_CHECKS = os.environ.get("SCHEDTALK_RUN_SCHEMA_CHECKS", "0") == "1"
USER_PROFILE_COLUMNS_READY = False

USER_PROFILE_COLUMNS = {
    "full_name": "ALTER TABLE users ADD COLUMN full_name VARCHAR(255) NOT NULL DEFAULT ''",
    "phone": "ALTER TABLE users ADD COLUMN phone VARCHAR(50) NOT NULL DEFAULT ''",
    "age": "ALTER TABLE users ADD COLUMN age INT NULL",
    "gender": "ALTER TABLE users ADD COLUMN gender VARCHAR(50) NOT NULL DEFAULT ''",
}


DEFAULT_PATIENTS = []

DEFAULT_APPOINTMENTS = []

BOOKING_TIME_SLOTS = [
    "08:00 AM",
    "09:00 AM",
    "10:00 AM",
    "11:00 AM",
    "12:00 PM",
    "01:00 PM",
    "02:00 PM",
    "03:00 PM",
    "04:00 PM",
    "05:00 PM",
]
DATA_DIR = Path(app.root_path) / "data"
DATA_FILE = DATA_DIR / "clinic_data.json"
ADMIN_PROFILES_FILE = DATA_DIR / "admin_profiles.json"
ADMIN_UPLOADS_DIR = Path(app.root_path) / "static" / "uploads" / "admin_profiles"
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
try:
    REMINDER_TIMEZONE = ZoneInfo("Asia/Singapore")
except ZoneInfoNotFoundError:
    # Fallback for environments where tzdata is not installed.
    REMINDER_TIMEZONE = timezone(timedelta(hours=8))
REMINDER_CHECK_INTERVAL_SECONDS = 300
REMINDER_24H_WINDOW_HOURS = 24
REMINDER_2H_WINDOW_HOURS = 2
REMINDER_MISSED_GRACE_MINUTES = 30
REMINDER_WORKER_STARTED = False
REMINDER_WORKER_LOCK = threading.Lock()


def ensure_data_file():
    DATA_DIR.mkdir(exist_ok=True)
    ADMIN_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(
            json.dumps(
                {
                    "patients": DEFAULT_PATIENTS,
                    "appointments": DEFAULT_APPOINTMENTS,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if not ADMIN_PROFILES_FILE.exists():
        ADMIN_PROFILES_FILE.write_text("{}", encoding="utf-8")


def load_data():
    ensure_data_file()
    with DATA_FILE.open("r", encoding="utf-8") as data_file:
        data = json.load(data_file)

    patients = data.get("patients") or deepcopy(DEFAULT_PATIENTS)
    appointments = data.get("appointments") or deepcopy(DEFAULT_APPOINTMENTS)
    return patients, appointments


def load_admin_profiles():
    ensure_data_file()
    with ADMIN_PROFILES_FILE.open("r", encoding="utf-8") as profiles_file:
        try:
            return json.load(profiles_file)
        except json.JSONDecodeError:
            return {}


def save_admin_profiles(admin_profiles):
    ensure_data_file()
    with ADMIN_PROFILES_FILE.open("w", encoding="utf-8") as profiles_file:
        json.dump(admin_profiles, profiles_file, indent=2)


def save_data():
    ensure_data_file()
    with DATA_FILE.open("w", encoding="utf-8") as data_file:
        json.dump(
            {
                "patients": PATIENTS,
                "appointments": APPOINTMENTS,
            },
            data_file,
            indent=2,
        )


def ensure_appointment_reminder_fields(appointment):
    appointment.setdefault("email", "")
    appointment.setdefault("reminder_sent", False)
    appointment.setdefault("reminder_sent_at", "")
    appointment.setdefault("reminder_24h_sent", False)
    appointment.setdefault("reminder_2h_sent", False)
    appointment.setdefault("missed_followup_sent", False)
    appointment.setdefault("last_reminder_error", "")


def normalize_appointments_schema():
    changed = False
    for appointment in APPOINTMENTS:
        before = dict(appointment)
        ensure_appointment_reminder_fields(appointment)
        if appointment != before:
            changed = True
    if changed:
        save_data()


PATIENTS, APPOINTMENTS = load_data()
normalize_appointments_schema()


def ensure_user_profile_columns():
    global USER_PROFILE_COLUMNS_READY
    if USER_PROFILE_COLUMNS_READY or not RUN_SCHEMA_CHECKS:
        return

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users'
            """,
            (app.config["MYSQL_DB"],),
        )
        existing_columns = {row[0] for row in cur.fetchall()}

        for column_name, alter_query in USER_PROFILE_COLUMNS.items():
            if column_name not in existing_columns:
                cur.execute(alter_query)

        mysql.connection.commit()
        cur.close()
        USER_PROFILE_COLUMNS_READY = True
    except Exception as error:
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        app.logger.warning("Skipping user profile column sync: %s", error)


def send_contact_email(name, email, message):
    mail_password = app.config["MAIL_PASSWORD"]
    if not mail_password or mail_password == "PASTE_YOUR_GMAIL_APP_PASSWORD_HERE":
        raise RuntimeError("Contact email is not configured yet.")

    email_message = EmailMessage()
    email_message["Subject"] = f"SchedTalk Contact Form - {name}"
    email_message["From"] = app.config["MAIL_USERNAME"]
    email_message["To"] = app.config["CONTACT_RECIPIENT"]
    email_message["Reply-To"] = email
    email_message.set_content(
        f"Name: {name}\n"
        f"Email: {email}\n\n"
        "Message:\n"
        f"{message}"
    )

    if app.config["MAIL_USE_SSL"]:
        with smtplib.SMTP_SSL(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]) as smtp:
            smtp.login(app.config["MAIL_USERNAME"], mail_password)
            smtp.send_message(email_message)
    else:
        with smtplib.SMTP(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]) as smtp:
            smtp.starttls()
            smtp.login(app.config["MAIL_USERNAME"], mail_password)
            smtp.send_message(email_message)


def parse_appointment_datetime(appointment):
    appointment_date = (appointment.get("date") or "").strip()
    appointment_time = (appointment.get("time") or "").strip()
    if not appointment_date or not appointment_time:
        return None

    time_formats = [
        "%I:%M %p",
        "%I:%M%p",
        "%H:%M",
        "%I %p",
        "%I%p",
    ]
    parsed_time = None
    for time_format in time_formats:
        try:
            parsed_time = datetime.strptime(
                appointment_time.replace(".", "").upper(),
                time_format,
            ).time()
            break
        except ValueError:
            continue

    if parsed_time is None:
        return None

    try:
        parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    return datetime.combine(parsed_date, parsed_time, tzinfo=REMINDER_TIMEZONE)


def send_automated_reminder_email(appointment, reminder_kind):
    mail_password = app.config["MAIL_PASSWORD"]
    if not mail_password or mail_password == "PASTE_YOUR_GMAIL_APP_PASSWORD_HERE":
        raise RuntimeError("Reminder email is not configured yet.")

    recipient_email = (appointment.get("email") or "").strip()
    if not recipient_email:
        raise RuntimeError("No email saved for this appointment.")

    clinic_name = os.environ.get("SCHEDTALK_CLINIC_NAME", "SchedTalk Clinic")
    patient_name = appointment.get("patient", "Patient")
    doctor_name = appointment.get("doctor", "Clinic Doctor")
    appointment_date = appointment.get("date", "")
    appointment_time = appointment.get("time", "")
    appointment_type = appointment.get("type", "")

    if reminder_kind == "24h":
        subject = f"24-Hour Appointment Reminder - {clinic_name}"
        body = (
            f"Hello {patient_name},\n\n"
            "This is a reminder that your appointment is in about 24 hours.\n\n"
            f"Date: {appointment_date}\n"
            f"Time: {appointment_time}\n"
            f"Doctor: {doctor_name}\n"
            f"Appointment Type: {appointment_type}\n\n"
            f"Clinic: {clinic_name}\n\n"
            "Please arrive a few minutes early.\n"
            "Thank you."
        )
    elif reminder_kind == "2h":
        subject = f"2-Hour Appointment Reminder - {clinic_name}"
        body = (
            f"Hello {patient_name},\n\n"
            "Your clinic appointment is coming up in around 2 hours.\n\n"
            f"Date: {appointment_date}\n"
            f"Time: {appointment_time}\n"
            f"Doctor: {doctor_name}\n"
            f"Appointment Type: {appointment_type}\n\n"
            f"Clinic: {clinic_name}\n\n"
            "See you soon."
        )
    else:
        subject = f"We Missed You - Reschedule Appointment at {clinic_name}"
        body = (
            f"Hello {patient_name},\n\n"
            "We noticed you may have missed your appointment.\n\n"
            f"Scheduled Date: {appointment_date}\n"
            f"Scheduled Time: {appointment_time}\n"
            f"Doctor: {doctor_name}\n"
            f"Appointment Type: {appointment_type}\n\n"
            "If you would like to reschedule, please contact the clinic.\n"
            f"Clinic: {clinic_name}\n\n"
            "Thank you."
        )

    reminder_email = EmailMessage()
    reminder_email["Subject"] = subject
    reminder_email["From"] = app.config["MAIL_USERNAME"]
    reminder_email["To"] = recipient_email
    reminder_email.set_content(body)

    if app.config["MAIL_USE_SSL"]:
        with smtplib.SMTP_SSL(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]) as smtp:
            smtp.login(app.config["MAIL_USERNAME"], mail_password)
            smtp.send_message(reminder_email)
    else:
        with smtplib.SMTP(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]) as smtp:
            smtp.starttls()
            smtp.login(app.config["MAIL_USERNAME"], mail_password)
            smtp.send_message(reminder_email)


def run_smart_reminder_engine_once():
    now = datetime.now(REMINDER_TIMEZONE)
    any_changes = False

    for appointment in APPOINTMENTS:
        ensure_appointment_reminder_fields(appointment)
        if appointment.get("status") not in {"Pending", "Scheduled"}:
            continue

        appointment_dt = parse_appointment_datetime(appointment)
        if appointment_dt is None:
            continue

        email_exists = bool((appointment.get("email") or "").strip())
        if not email_exists:
            continue

        hours_until = (appointment_dt - now).total_seconds() / 3600

        try:
            if (
                0 < hours_until <= REMINDER_24H_WINDOW_HOURS
                and hours_until > REMINDER_2H_WINDOW_HOURS
                and not appointment.get("reminder_24h_sent")
            ):
                send_automated_reminder_email(appointment, "24h")
                appointment["reminder_24h_sent"] = True
                appointment["last_reminder_error"] = ""
                any_changes = True

            if (
                0 < hours_until <= REMINDER_2H_WINDOW_HOURS
                and not appointment.get("reminder_2h_sent")
            ):
                send_automated_reminder_email(appointment, "2h")
                appointment["reminder_2h_sent"] = True
                appointment["last_reminder_error"] = ""
                any_changes = True

            missed_threshold = appointment_dt + timedelta(minutes=REMINDER_MISSED_GRACE_MINUTES)
            if now >= missed_threshold and not appointment.get("missed_followup_sent"):
                send_automated_reminder_email(appointment, "missed")
                appointment["missed_followup_sent"] = True
                appointment["last_reminder_error"] = ""
                any_changes = True
        except Exception as error:
            appointment["last_reminder_error"] = str(error)
            any_changes = True
            app.logger.warning(
                "Smart reminder send failed for appointment %s: %s",
                appointment.get("id"),
                error,
            )

    if any_changes:
        save_data()


def smart_reminder_worker():
    while True:
        try:
            with app.app_context():
                run_smart_reminder_engine_once()
        except Exception as error:
            app.logger.warning("Smart reminder worker loop failed: %s", error)
        time.sleep(REMINDER_CHECK_INTERVAL_SECONDS)


def start_smart_reminder_worker():
    global REMINDER_WORKER_STARTED
    with REMINDER_WORKER_LOCK:
        if REMINDER_WORKER_STARTED:
            return
        reminder_thread = threading.Thread(
            target=smart_reminder_worker,
            name="smart-reminder-worker",
            daemon=True,
        )
        reminder_thread.start()
        REMINDER_WORKER_STARTED = True


def generate_otp():
    return str(random.randint(100000, 999999))


def hash_text(value):
    return sha256(value.encode("utf-8")).hexdigest()


def verify_password(saved_password, incoming_password):
    if not saved_password:
        return False
    if saved_password.startswith("pbkdf2:") or saved_password.startswith("scrypt:"):
        return check_password_hash(saved_password, incoming_password)
    return saved_password == incoming_password


def send_otp_email(email, otp):
    resend_api_key = app.config["RESEND_API_KEY"]
    resend_success = False

    if resend_api_key:
        payload = json.dumps(
            {
                "from": app.config["OTP_FROM_EMAIL"],
                "to": [email],
                "subject": "Your OTP Code",
                "html": f"<h3>Your OTP is: {otp}</h3><p>Expires in 5 minutes.</p>",
            }
        )
        request_data = Request(
            "https://api.resend.com/emails",
            data=payload.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request_data, timeout=10) as response:
                resend_success = 200 <= response.status < 300
                if resend_success:
                    return True
        except HTTPError as error:
            error_body = ""
            try:
                error_body = error.read().decode("utf-8", errors="replace")
            except Exception:
                error_body = "<unable to read response body>"
            app.logger.warning(
                "Resend OTP failed (HTTPError %s): %s | response=%s",
                error.code,
                error.reason,
                error_body,
            )
        except URLError as error:
            app.logger.warning("Resend OTP failed (URLError): %s", error.reason)
        except TimeoutError:
            app.logger.warning("Resend OTP failed (TimeoutError)")
        except Exception as error:
            app.logger.warning("Resend OTP failed (unexpected): %s", error)
    else:
        app.logger.warning("Resend OTP skipped: RESEND_API_KEY is not set")

    mail_password = app.config["MAIL_PASSWORD"]
    if not mail_password or mail_password == "PASTE_YOUR_GMAIL_APP_PASSWORD_HERE":
        app.logger.warning("SMTP OTP fallback skipped: MAIL_PASSWORD is not configured")
        return False

    otp_email = EmailMessage()
    otp_email["Subject"] = "Your OTP Code"
    otp_email["From"] = app.config["MAIL_USERNAME"]
    otp_email["To"] = email
    otp_email.set_content(
        "Your one-time password is: "
        f"{otp}\n\n"
        "This code expires in 5 minutes."
    )

    try:
        mail_timeout = app.config["MAIL_TIMEOUT_SECONDS"]
        if app.config["MAIL_USE_SSL"]:
            with smtplib.SMTP_SSL(
                app.config["MAIL_SERVER"], app.config["MAIL_PORT"], timeout=mail_timeout
            ) as smtp:
                smtp.login(app.config["MAIL_USERNAME"], mail_password)
                smtp.send_message(otp_email)
        else:
            with smtplib.SMTP(
                app.config["MAIL_SERVER"], app.config["MAIL_PORT"], timeout=mail_timeout
            ) as smtp:
                smtp.starttls()
                smtp.login(app.config["MAIL_USERNAME"], mail_password)
                smtp.send_message(otp_email)
        app.logger.info("OTP sent via SMTP fallback to %s", email)
        return True
    except Exception as error:
        app.logger.warning("SMTP OTP fallback failed: %s", error)
        return resend_success


def fetch_user_by_username(username):
    ensure_user_profile_columns()
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT
            id,
            username,
            password,
            email,
            role,
            full_name,
            phone,
            age,
            gender
        FROM users
        WHERE username = %s
        """,
        (username,),
    )
    user = cur.fetchone()
    cur.close()
    return user


def fetch_user_by_email(email):
    ensure_user_profile_columns()
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT
            id,
            username,
            password,
            email,
            role,
            full_name,
            phone,
            age,
            gender
        FROM users
        WHERE email = %s
        """,
        (email,),
    )
    user = cur.fetchone()
    cur.close()
    return user


def begin_otp_for_user(user, username_for_redirect):
    user_email = (user[3] or "").strip()
    if not user_email:
        return redirect(url_for("index", login_error="no_email"))

    otp = generate_otp()
    if not send_otp_email(user_email, otp):
        return redirect(url_for("index", login_error="otp_send_failed", username=username_for_redirect))

    session["pending_otp_hash"] = hash_text(otp)
    session["pending_otp_expiry"] = time.time() + app.config["OTP_EXPIRE_SECONDS"]
    session["pending_otp_attempts"] = 0
    session["pending_user"] = {
        "account_username": user[1],
        "username": user[1],
        "email": user_email,
        "role": "admin" if user[1] == "admin01" else (user[4] or "user"),
        "full_name": user[5] or user[1],
        "phone": user[6] or "",
        "age": user[7],
        "gender": user[8] or "",
    }
    return redirect(url_for("index", otp_required="1", username=username_for_redirect))


def make_unique_username(base_username):
    base = "".join(char.lower() if char.isalnum() else "_" for char in base_username).strip("_")
    if not base:
        base = "user"

    candidate = base
    suffix = 1
    while fetch_user_by_username(candidate):
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def is_admin():
    return session.get("loggedin") and session.get("role") == "admin"


def admin_guard():
    if not is_admin():
        return redirect(url_for("index"))
    return None


def next_patient_id():
    return max((patient["id"] for patient in PATIENTS), default=0) + 1


def next_appointment_id():
    return max((appointment["id"] for appointment in APPOINTMENTS), default=0) + 1


def normalize_patient_name(name):
    return " ".join((name or "").strip().lower().split())


def fetch_user_email_lookup():
    ensure_user_profile_columns()
    lookup = {}
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            """
            SELECT username, email, full_name
            FROM users
            """
        )
        for row in cur.fetchall():
            username = normalize_patient_name(row[0] or "")
            email = (row[1] or "").strip()
            full_name = normalize_patient_name(row[2] or "")
            if email:
                if full_name and full_name not in lookup:
                    lookup[full_name] = email
                if username and username not in lookup:
                    lookup[username] = email
        cur.close()
    except Exception as error:
        app.logger.warning("Unable to load user email lookup: %s", error)
    return lookup


def find_patient(patient_id):
    return next(
        (patient for patient in PATIENTS if patient.get("id") == patient_id),
        None,
    )


def appointments_for_patient(patient):
    patient_name = normalize_patient_name(patient.get("name", ""))
    return [
        appointment
        for appointment in APPOINTMENTS
        if normalize_patient_name(appointment.get("patient", "")) == patient_name
    ]


def initials_for(name):
    words = [word for word in name.split() if word]
    return "".join(word[0].upper() for word in words[:2]) or "AD"


def admin_account_key():
    return session.get("account_username") or session.get("username", "admin01")


def profile_image_url(profile_image_path):
    if not profile_image_path:
        return ""

    image_file = Path(app.root_path) / "static" / profile_image_path.replace("/", os.sep)
    if not image_file.exists():
        return ""

    return url_for("static", filename=profile_image_path.replace("\\", "/"))


def get_saved_admin_profile(account_username=None):
    profile_key = account_username or admin_account_key()
    admin_profiles = load_admin_profiles()
    return admin_profiles.get(profile_key, {})


def persist_admin_profile(account_username, profile_updates):
    admin_profiles = load_admin_profiles()
    existing_profile = admin_profiles.get(account_username, {})
    existing_profile.update(profile_updates)
    admin_profiles[account_username] = existing_profile
    save_admin_profiles(admin_profiles)
    return existing_profile


def save_admin_profile_image(account_username, image_file):
    original_name = secure_filename(image_file.filename or "")
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_PROFILE_IMAGE_EXTENSIONS:
        raise ValueError("Please upload a PNG, JPG, JPEG, GIF, or WEBP image.")

    unique_name = f"{secure_filename(account_username)}_{uuid4().hex}{extension}"
    destination = ADMIN_UPLOADS_DIR / unique_name
    image_file.save(destination)
    return f"uploads/admin_profiles/{unique_name}"


def apply_admin_profile_to_session(account_username, default_username=None, default_email=None):
    saved_profile = get_saved_admin_profile(account_username)

    session["account_username"] = account_username
    session["username"] = (
        saved_profile.get("display_name")
        or session.get("username")
        or default_username
        or account_username
    )
    session["email"] = (
        saved_profile.get("email")
        or session.get("email")
        or default_email
        or ""
    )
    session["clinic_name"] = (
        saved_profile.get("clinic_name")
        or session.get("clinic_name")
        or "SchedTalk Clinic"
    )
    session["contact_number"] = (
        saved_profile.get("contact_number")
        or session.get("contact_number")
        or "+63 912 000 0000"
    )
    session["profile_pic"] = saved_profile.get("profile_image", "") or ""


def build_admin_summary():
    today_iso = date.today().isoformat()
    current_month = today_iso[:7]
    target_weekly_goal = 25
    week_dates = [date.today() - timedelta(days=offset) for offset in range(6, -1, -1)]
    last_week_dates = [booking_date - timedelta(days=7) for booking_date in week_dates]
    today_appointments = [
        appointment for appointment in APPOINTMENTS if appointment["date"] == today_iso
    ]
    today_active_appointments = [
        appointment
        for appointment in today_appointments
        if appointment["status"] in {"Pending", "Scheduled"}
    ]
    pending_count = sum(
        1
        for appointment in APPOINTMENTS
        if appointment["status"] in {"Pending", "Scheduled"}
    )
    completed_count = sum(
        1
        for appointment in today_appointments
        if appointment["status"] == "Completed"
    )
    cancelled_count = sum(
        1
        for appointment in today_appointments
        if appointment["status"] == "Cancelled"
    )

    recent_appointments = sorted(
        APPOINTMENTS, key=lambda appointment: (appointment["date"], appointment["time"]), reverse=True
    )[:5]

    def unique_patient_count(appointments):
        return len(
            {
                appointment["patient"].strip().lower()
                for appointment in appointments
                if appointment.get("patient", "").strip()
            }
        )

    upcoming_appointments = [
        appointment
        for appointment in APPOINTMENTS
        if appointment["status"] in {"Pending", "Scheduled"}
        and appointment["date"] >= today_iso
    ]
    completed_today_appointments = [
        appointment
        for appointment in today_appointments
        if appointment["status"] == "Completed"
    ]
    completed_this_month_appointments = [
        appointment
        for appointment in APPOINTMENTS
        if appointment["status"] == "Completed"
        and appointment["date"].startswith(current_month)
    ]

    patient_status_counts = {
        "total": len(PATIENTS),
        "upcoming": unique_patient_count(upcoming_appointments),
        "completed_today": unique_patient_count(completed_today_appointments),
        "completed_this_month": unique_patient_count(completed_this_month_appointments),
    }
    weekly_bookings = []
    for booking_date in week_dates:
        booking_date_iso = booking_date.isoformat()
        day_count = sum(
            1 for appointment in APPOINTMENTS if appointment.get("date") == booking_date_iso
        )
        weekly_bookings.append(
            {
                "day": booking_date.strftime("%a"),
                "date": booking_date_iso,
                "count": day_count,
            }
        )
    last_week_bookings = []
    for booking_date in last_week_dates:
        booking_date_iso = booking_date.isoformat()
        day_count = sum(
            1 for appointment in APPOINTMENTS if appointment.get("date") == booking_date_iso
        )
        last_week_bookings.append(
            {
                "day": booking_date.strftime("%a"),
                "date": booking_date_iso,
                "count": day_count,
            }
        )

    return {
        "stats": {
            "today": len(today_active_appointments),
            "pending": pending_count,
            "completed": completed_count,
            "cancelled": cancelled_count,
        },
        "today_appointments": today_appointments,
        "recent_appointments": recent_appointments,
        "patient_status_counts": patient_status_counts,
        "today_label": date.today().strftime("%B %d, %Y"),
        "weekly_bookings": weekly_bookings,
        "last_week_bookings": last_week_bookings,
        "target_weekly_goal": target_weekly_goal,
    }


def serialize_dashboard_summary(summary):
    return {
        "stats": summary["stats"],
        "today_label": summary["today_label"],
        "weekly_bookings": summary["weekly_bookings"],
        "last_week_bookings": summary["last_week_bookings"],
        "target_weekly_goal": summary["target_weekly_goal"],
        "today_appointments": [
            {
                "id": appointment["id"],
                "patient": appointment["patient"],
                "doctor": appointment["doctor"],
                "type": appointment["type"],
                "time": appointment["time"],
                "status": appointment["status"],
                "status_class": appointment["status"].lower().replace(" ", "-"),
            }
            for appointment in summary["today_appointments"]
        ],
    }


def parse_days_filter(raw_days):
    allowed = {7, 30, 90}
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return 7
    return days if days in allowed else 7


def build_graphs_payload(days=7, doctor_filter="all"):
    today = date.today()
    selected_days = parse_days_filter(days)
    normalized_doctor = (doctor_filter or "all").strip().lower()
    doctor_options = sorted(
        {
            (appointment.get("doctor") or "").strip()
            for appointment in APPOINTMENTS
            if (appointment.get("doctor") or "").strip()
        }
    )

    def within_date_range(appointment, start_date, end_date):
        try:
            appointment_date = datetime.strptime(
                (appointment.get("date") or "").strip(),
                "%Y-%m-%d",
            ).date()
        except ValueError:
            return False
        return start_date <= appointment_date <= end_date

    def doctor_matches(appointment):
        if normalized_doctor == "all":
            return True
        return (appointment.get("doctor") or "").strip().lower() == normalized_doctor

    period_start = today - timedelta(days=selected_days - 1)
    period_end = today
    previous_period_end = period_start - timedelta(days=1)
    previous_period_start = previous_period_end - timedelta(days=selected_days - 1)

    current_period_appointments = [
        appointment
        for appointment in APPOINTMENTS
        if within_date_range(appointment, period_start, period_end)
        and doctor_matches(appointment)
    ]
    previous_period_appointments = [
        appointment
        for appointment in APPOINTMENTS
        if within_date_range(appointment, previous_period_start, previous_period_end)
        and doctor_matches(appointment)
    ]

    current_dates = [period_start + timedelta(days=offset) for offset in range(selected_days)]
    previous_dates = [previous_period_start + timedelta(days=offset) for offset in range(selected_days)]

    def count_for_date(appointments, target_date):
        target_iso = target_date.isoformat()
        return sum(1 for item in appointments if (item.get("date") or "") == target_iso)

    weekly_bookings = [
        {
            "day": target_date.strftime("%a"),
            "date": target_date.isoformat(),
            "count": count_for_date(current_period_appointments, target_date),
        }
        for target_date in current_dates
    ]
    last_week_bookings = [
        {
            "day": target_date.strftime("%a"),
            "date": target_date.isoformat(),
            "count": count_for_date(previous_period_appointments, target_date),
        }
        for target_date in previous_dates
    ]

    total_bookings = len(current_period_appointments)
    completed = sum(
        1 for appointment in current_period_appointments if (appointment.get("status") or "") == "Completed"
    )
    cancelled = sum(
        1 for appointment in current_period_appointments if (appointment.get("status") or "") == "Cancelled"
    )
    no_show = sum(
        1
        for appointment in current_period_appointments
        if "no show" in (appointment.get("status") or "").strip().lower().replace("-", " ")
    )

    completion_rate = round((completed / total_bookings) * 100, 1) if total_bookings else 0.0
    cancellation_rate = round((cancelled / total_bookings) * 100, 1) if total_bookings else 0.0
    no_show_rate = round((no_show / total_bookings) * 100, 1) if total_bookings else 0.0

    busiest_day = max(weekly_bookings, key=lambda item: item["count"], default=None)
    quietest_day = min(weekly_bookings, key=lambda item: item["count"], default=None)
    previous_total = len(previous_period_appointments)
    delta = total_bookings - previous_total

    if delta > 0:
        trend_text = f"Bookings are up by {delta} versus the previous {selected_days} days."
    elif delta < 0:
        trend_text = f"Bookings are down by {abs(delta)} versus the previous {selected_days} days."
    else:
        trend_text = f"Bookings are unchanged versus the previous {selected_days} days."

    insights = [
        trend_text,
        (
            f"Busiest day: {busiest_day['day']} ({busiest_day['date'][5:]}), "
            f"{busiest_day['count']} bookings."
            if busiest_day
            else "No bookings in the selected period yet."
        ),
        (
            f"Quietest day: {quietest_day['day']} ({quietest_day['date'][5:]}), "
            f"{quietest_day['count']} bookings."
            if quietest_day
            else "No quiet-day insight available."
        ),
    ]

    return {
        "days": selected_days,
        "doctor": normalized_doctor,
        "doctor_options": doctor_options,
        "weekly_bookings": weekly_bookings,
        "last_week_bookings": last_week_bookings,
        "kpis": {
            "total_bookings": total_bookings,
            "completion_rate": completion_rate,
            "cancellation_rate": cancellation_rate,
            "no_show_rate": no_show_rate,
        },
        "insights": insights,
    }


def build_patient_history(patient):
    today_iso = date.today().isoformat()
    patient_appointments = sorted(
        appointments_for_patient(patient),
        key=lambda appointment: (appointment.get("date", ""), appointment.get("time", "")),
        reverse=True,
    )
    upcoming_appointments = sorted(
        [
            appointment
            for appointment in patient_appointments
            if appointment.get("status") in {"Pending", "Scheduled"}
            and appointment.get("date", "") >= today_iso
        ],
        key=lambda appointment: (appointment.get("date", ""), appointment.get("time", "")),
    )
    next_appointment = upcoming_appointments[0] if upcoming_appointments else None

    return {
        "appointments": patient_appointments,
        "next_appointment": next_appointment,
        "counts": {
            "total": len(patient_appointments),
            "completed": sum(
                1
                for appointment in patient_appointments
                if appointment.get("status") == "Completed"
            ),
            "cancelled": sum(
                1
                for appointment in patient_appointments
                if appointment.get("status") == "Cancelled"
            ),
            "upcoming": len(upcoming_appointments),
        },
    }


def find_appointment(appointment_id):
    return next(
        (appointment for appointment in APPOINTMENTS if appointment["id"] == appointment_id),
        None,
    )


def admin_profile():
    username = session.get("username", "Admin User")
    email = session.get("email", "admin@schedtalk.com")
    profile_pic = session.get("profile_pic", "")
    return {
        "username": username,
        "email": email,
        "initials": initials_for(username),
        "profile_image_url": profile_image_url(profile_pic),
    }


def appointment_blocks_date(appointment):
    return appointment["status"] != "Cancelled"


def appointment_shows_in_calendar(appointment):
    return appointment["status"] in {"Pending", "Scheduled"}


def normalize_booking_time_slot(raw_time):
    candidate = (raw_time or "").strip().upper().replace(".", "")
    if not candidate:
        return ""

    for time_format in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
        try:
            parsed = datetime.strptime(candidate, time_format)
            return parsed.strftime("%I:%M %p")
        except ValueError:
            continue

    return candidate


def is_time_slot_taken(appointment_date, appointment_time):
    normalized_requested_time = normalize_booking_time_slot(appointment_time)
    return any(
        appointment["date"] == appointment_date
        and normalize_booking_time_slot(appointment.get("time")) == normalized_requested_time
        and appointment_blocks_date(appointment)
        for appointment in APPOINTMENTS
    )


def build_booking_calendar_data(days_ahead=180):
    today_date = date.today()
    available_slots_by_date = {}
    initial_date = None

    for offset in range(days_ahead + 1):
        current_date = today_date + timedelta(days=offset)
        current_iso = current_date.isoformat()
        taken_times = {
            normalize_booking_time_slot(appointment.get("time"))
            for appointment in APPOINTMENTS
            if appointment["date"] == current_iso and appointment_blocks_date(appointment)
        }
        available_slots = [
            time_slot for time_slot in BOOKING_TIME_SLOTS if time_slot not in taken_times
        ]
        available_slots_by_date[current_iso] = available_slots
        if initial_date is None and available_slots:
            initial_date = current_iso

    if initial_date is None:
        initial_date = today_date.isoformat()

    return {
        "available_slots_by_date": available_slots_by_date,
        "initial_date": initial_date,
    }


def get_available_slots_for_date(appointment_date):
    taken_times = {
        normalize_booking_time_slot(appointment.get("time"))
        for appointment in APPOINTMENTS
        if appointment["date"] == appointment_date and appointment_blocks_date(appointment)
    }
    return [
        time_slot for time_slot in BOOKING_TIME_SLOTS if time_slot not in taken_times
    ]


def build_upcoming_availability(limit=5, days_ahead=30):
    today_date = date.today()
    upcoming = []

    for offset in range(days_ahead + 1):
        current_date = today_date + timedelta(days=offset)
        current_iso = current_date.isoformat()
        slots = get_available_slots_for_date(current_iso)
        if slots:
            upcoming.append(
                {
                    "date": current_iso,
                    "label": current_date.strftime("%A, %B %d, %Y"),
                    "slots": slots,
                }
            )
        if len(upcoming) >= limit:
            break

    return upcoming


def build_chatbot_system_prompt():
    upcoming = build_upcoming_availability(limit=3, days_ahead=14)
    availability_lines = []
    for entry in upcoming:
        availability_lines.append(f"{entry['date']} ({entry['label']}): {', '.join(entry['slots'])}")

    availability_context = "\n".join(availability_lines) if availability_lines else "No open slots found."
    profile_name = session.get("full_name") or session.get("username") or "the patient"
    known_doctors = sorted(
        {
            appointment.get("doctor", "").strip()
            for appointment in APPOINTMENTS
            if appointment.get("doctor", "").strip()
        }
    )
    doctor_context = ", ".join(known_doctors) if known_doctors else "No doctor list is available yet."

    return (
        "You are SchedTalk's AI assistant for a clinic.\n"
        "Your primary role is scheduling appointments, but you can answer general questions too.\n"
        "Speak naturally and warmly like a real helpful person, not a scripted bot.\n"
        "For casual/general questions: answer directly in a friendly way.\n"
        "For scheduling questions: prioritize accurate booking guidance and available times.\n"
        "If the user wants to book, ask for consultation type, date (YYYY-MM-DD), and time.\n"
        "If asked about schedule availability, use only the known availability context below.\n"
        "Never invent unavailable slots.\n"
        "If asked about doctors, use the known doctor list. If unknown, say you do not have a confirmed doctor name yet.\n"
        "Keep replies concise (usually 2-5 sentences) and empathetic.\n"
        "Avoid sounding repetitive, formal, or robotic.\n\n"
        f"Logged-in patient display name: {profile_name}\n"
        f"Known doctors: {doctor_context}\n"
        "Known upcoming availability:\n"
        f"{availability_context}"
    )


def upsert_patient_record(name, phone, condition, age=None, gender=None):
    existing_patient = next(
        (patient for patient in PATIENTS if patient["name"].lower() == name.lower()),
        None,
    )

    parsed_age = 0
    if age not in (None, ""):
        try:
            parsed_age = max(int(age), 0)
        except (TypeError, ValueError):
            parsed_age = 0

    patient_gender = gender.strip() if isinstance(gender, str) and gender.strip() else "Not set"

    if existing_patient:
        existing_patient["phone"] = phone
        existing_patient["status"] = "Scheduled"
        existing_patient["condition"] = condition
        if parsed_age:
            existing_patient["age"] = parsed_age
        if patient_gender != "Not set":
            existing_patient["gender"] = patient_gender
        return existing_patient

    patient_record = {
        "id": next_patient_id(),
        "name": name,
        "age": parsed_age,
        "gender": patient_gender,
        "phone": phone,
        "status": "Scheduled",
        "condition": condition,
    }
    PATIENTS.append(patient_record)
    return patient_record


def create_appointment_booking(
    patient_name,
    patient_email,
    patient_phone,
    appointment_date,
    appointment_time,
    appointment_type,
    notes="",
    age=None,
    gender=None,
):
    normalized_time = normalize_booking_time_slot(appointment_time)

    if is_time_slot_taken(appointment_date, appointment_time):
        return None

    APPOINTMENTS.append(
        {
            "id": next_appointment_id(),
            "patient": patient_name,
            "email": patient_email.strip() if isinstance(patient_email, str) else "",
            "doctor": "Dr. Carlos Sy",
            "specialty": "General Consultation",
            "date": appointment_date,
            "time": normalized_time or appointment_time,
            "type": appointment_type,
            "status": "Scheduled",
            "notes": notes.strip() if isinstance(notes, str) else "",
            "reminder_sent": False,
            "reminder_sent_at": "",
        }
    )

    upsert_patient_record(
        name=patient_name,
        phone=patient_phone,
        condition=notes or appointment_type,
        age=age,
        gender=gender,
    )

    if patient_email:
        session["email"] = patient_email

    save_data()
    return {
        "patient": patient_name,
        "email": patient_email,
        "phone": patient_phone,
        "date": appointment_date,
        "time": normalized_time or appointment_time,
        "type": appointment_type,
    }


# --- ROUTES ---
@app.before_request
def ensure_background_workers():
    start_smart_reminder_worker()


@app.route("/")
def index():
    return render_template(
        "home.html",
        login_required=request.args.get("login_required") == "1",
        login_error=request.args.get("login_error", ""),
        login_username=request.args.get("username", ""),
        signup_error=request.args.get("signup_error", ""),
        signup_success=request.args.get("signup_success") == "1",
        signup_username=request.args.get("signup_username", ""),
        signup_firstname=request.args.get("signup_firstname", ""),
        signup_middleinitial=request.args.get("signup_middleinitial", ""),
        signup_lastname=request.args.get("signup_lastname", ""),
        signup_email=request.args.get("signup_email", ""),
        signup_phone=request.args.get("signup_phone", ""),
        signup_age=request.args.get("signup_age", ""),
        signup_gender=request.args.get("signup_gender", ""),
        contact_error=request.args.get("contact_error", ""),
        contact_sent=request.args.get("contact_sent") == "1",
        contact_name=request.args.get("contact_name", ""),
        contact_email=request.args.get("contact_email", ""),
        contact_message=request.args.get("contact_message", ""),
        otp_required=request.args.get("otp_required") == "1",
        otp_error=request.args.get("otp_error", ""),
        chatbot_logged_in=bool(session.get("loggedin")),
        chatbot_profile={
            "name": session.get("full_name") or session.get("username", ""),
            "email": session.get("email", ""),
            "phone": session.get("phone", ""),
            "age": session.get("age"),
            "gender": session.get("gender", ""),
        },
    )


@app.route("/contact", methods=["POST"])
def contact():
    if not session.get("loggedin"):
        return redirect(url_for("index", login_required="1") + "#contact")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not email or not message:
        return redirect(
            url_for(
                "index",
                contact_error="Please complete all contact form fields.",
                contact_name=name,
                contact_email=email,
                contact_message=message,
            )
            + "#contact"
        )

    try:
        send_contact_email(name, email, message)
    except Exception:
        return redirect(
            url_for(
                "index",
                contact_error="We could not send your email right now. Please check the mail setup and try again.",
                contact_name=name,
                contact_email=email,
                contact_message=message,
            )
            + "#contact"
        )

    return redirect(url_for("index", contact_sent="1") + "#contact")


@app.route("/booking")
def booking():
    if not session.get("loggedin"):
        return redirect(url_for("index", login_required="1"))

    calendar_data = build_booking_calendar_data()
    initial_times = calendar_data["available_slots_by_date"].get(
        calendar_data["initial_date"], BOOKING_TIME_SLOTS[:]
    )
    return render_template(
        "booking.html",
        available_times=initial_times,
        today_value=calendar_data["initial_date"],
        booking_success=request.args.get("booked") == "1",
        booking_error=request.args.get("date_unavailable") == "1",
        profile_name=session.get("full_name") or session.get("username", ""),
        profile_email=session.get("email", ""),
        profile_phone=session.get("phone", ""),
        available_slots_by_date=calendar_data["available_slots_by_date"],
    )


@app.route("/booking", methods=["POST"])
def submit_booking():
    if not session.get("loggedin"):
        return redirect(url_for("index", login_required="1"))

    patient_name = request.form["name"].strip()
    patient_email = request.form["email"].strip()
    patient_phone = request.form["phone"].strip()
    appointment_date = request.form["appointment_date"]
    appointment_time = request.form["appointment_time"].strip()
    appointment_time = normalize_booking_time_slot(appointment_time) or appointment_time
    appointment_type = request.form["appointment_type"].strip()
    notes = request.form["notes"].strip()

    if is_time_slot_taken(appointment_date, appointment_time):
        return redirect(url_for("booking", date_unavailable="1"))

    create_appointment_booking(
        patient_name=patient_name,
        patient_email=patient_email,
        patient_phone=patient_phone,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        appointment_type=appointment_type,
        notes=notes,
        age=session.get("age"),
        gender=session.get("gender", ""),
    )
    return redirect(url_for("booking", booked="1"))


@app.route("/api/availability")
def api_availability():
    if not session.get("loggedin"):
        return jsonify({"success": False, "message": "Please login to use the chatbot."}), 401

    appointment_date = request.args.get("date", "").strip()
    if appointment_date:
        return jsonify(
            {
                "date": appointment_date,
                "slots": get_available_slots_for_date(appointment_date),
            }
        )

    return jsonify({"upcoming": build_upcoming_availability()})


@app.route("/api/chatbot/book", methods=["POST"])
def chatbot_book():
    if not session.get("loggedin"):
        return jsonify({"success": False, "message": "Please login to use the chatbot."}), 401

    payload = request.get_json(silent=True) or {}

    required_fields = {
        "appointment_date": "Appointment date",
        "appointment_time": "Appointment time",
        "appointment_type": "Appointment type",
    }

    missing_fields = [
        label
        for key, label in required_fields.items()
        if not str(payload.get(key, "")).strip()
    ]
    if missing_fields:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Missing required information: {', '.join(missing_fields)}.",
                }
            ),
            400,
        )

    patient_name = (
        session.get("full_name")
        or session.get("username")
        or str(payload.get("name", "")).strip()
        or "SchedTalk Patient"
    )
    patient_email = session.get("email", "") or str(payload.get("email", "")).strip()
    patient_phone = session.get("phone", "") or str(payload.get("phone", "")).strip()

    booking = create_appointment_booking(
        patient_name=patient_name,
        patient_email=patient_email,
        patient_phone=patient_phone,
        appointment_date=str(payload["appointment_date"]).strip(),
        appointment_time=str(payload["appointment_time"]).strip(),
        appointment_type=str(payload["appointment_type"]).strip(),
        notes=str(payload.get("notes", "")).strip(),
        age=session.get("age"),
        gender=session.get("gender", ""),
    )

    if not booking:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "That time slot is no longer available. Please choose another schedule.",
                    "available_slots": get_available_slots_for_date(
                        str(payload["appointment_date"]).strip()
                    ),
                }
            ),
            409,
        )

    return jsonify(
        {
            "success": True,
            "message": "Your appointment has been booked successfully.",
            "booking": booking,
        }
    )


@app.route("/api/chatbot/respond", methods=["POST"])
def chatbot_respond():
    if not session.get("loggedin"):
        return jsonify({"success": False, "message": "Please login to use the chatbot."}), 401

    payload = request.get_json(silent=True) or {}
    user_message = str(payload.get("message", "")).strip()
    user_name = str(payload.get("user_name", "")).strip()
    preferred_tone = str(payload.get("preferred_tone", "warm")).strip().lower()
    if not user_message:
        return jsonify({"success": False, "message": "Please send a message."}), 400

    api_key = app.config["GROQ_API_KEY"]
    if not api_key or Groq is None:
        return jsonify(
            {
                "success": True,
                "reply": "I can help with scheduling. Ask me for available schedules or send booking details: consultation type, date, and time.",
            }
        )

    try:
        client = Groq(api_key=api_key)
        tone_instruction = "Use a warm and friendly tone."
        if preferred_tone == "concise":
            tone_instruction = "Use a concise tone with short direct answers."
        elif preferred_tone == "reassuring":
            tone_instruction = "Use a calm, reassuring, supportive tone."

        personalization = ""
        if user_name:
            personalization = f"The user's preferred name is {user_name}. Address them naturally when appropriate."

        completion = client.chat.completions.create(
            model=app.config["GROQ_MODEL"],
            temperature=0.7,
            max_completion_tokens=260,
            messages=[
                {
                    "role": "system",
                    "content": (
                        build_chatbot_system_prompt()
                        + "\n"
                        + tone_instruction
                        + ("\n" + personalization if personalization else "")
                    ),
                },
                {"role": "user", "content": user_message},
            ],
        )
        reply = completion.choices[0].message.content if completion.choices else ""
        if not reply:
            reply = "I can help with schedules and booking. Tell me your consultation, date, and time."
        return jsonify({"success": True, "reply": reply.strip()})
    except Exception as error:
        app.logger.warning("Groq chatbot failed: %s", error)
        return jsonify(
            {
                "success": True,
                "reply": "I can still help with booking and schedules right now. Please ask for availability or provide consultation, date, and time.",
            }
        )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin/dashboard")
def admin_dashboard():
    guard = admin_guard()
    if guard:
        return guard

    summary = build_admin_summary()
    return render_template(
        "admin_dashboard.html",
        active_page="dashboard",
        profile=admin_profile(),
        **summary,
    )


@app.route("/admin/dashboard/summary")
def admin_dashboard_summary():
    guard = admin_guard()
    if guard:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    return jsonify(
        {
            "success": True,
            "summary": serialize_dashboard_summary(build_admin_summary()),
        }
    )


@app.route("/admin/graphs")
def admin_graphs():
    guard = admin_guard()
    if guard:
        return guard

    days = parse_days_filter(request.args.get("days", "7"))
    doctor = request.args.get("doctor", "all")
    graphs_payload = build_graphs_payload(days=days, doctor_filter=doctor)
    return render_template(
        "admin_graphs.html",
        active_page="graphs",
        profile=admin_profile(),
        graphs_payload=graphs_payload,
    )


@app.route("/admin/graphs/data")
def admin_graphs_data():
    guard = admin_guard()
    if guard:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    days = parse_days_filter(request.args.get("days", "7"))
    doctor = request.args.get("doctor", "all")
    payload = build_graphs_payload(days=days, doctor_filter=doctor)
    return jsonify({"success": True, "data": payload})


@app.route("/admin/calendar", methods=["GET", "POST"])
def admin_calendar():
    guard = admin_guard()
    if guard:
        return guard

    if request.method == "POST":
        patient = request.form["patient"].strip()
        patient_email = request.form.get("email", "").strip()
        age = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        doctor = request.form["doctor"].strip()
        appointment_date = request.form["date"]
        appointment_time = request.form["time"].strip()
        appointment_time = normalize_booking_time_slot(appointment_time) or appointment_time
        appointment_type = request.form["type"].strip()

        if is_time_slot_taken(appointment_date, appointment_time):
            return redirect(url_for("admin_calendar", date_unavailable="1"))

        APPOINTMENTS.append(
            {
                "id": next_appointment_id(),
                "patient": patient,
                "email": patient_email,
                "doctor": doctor,
                "specialty": appointment_type,
                "date": appointment_date,
                "time": appointment_time,
                "type": appointment_type,
                "status": "Scheduled",
                "notes": appointment_type,
                "reminder_sent": False,
                "reminder_sent_at": "",
            }
        )
        upsert_patient_record(
            name=patient,
            phone=phone,
            condition=appointment_type,
            age=age,
            gender=gender,
        )
        save_data()
        return redirect(url_for("admin_calendar", created="1"))

    appointments = sorted(
        (
            appointment
            for appointment in APPOINTMENTS
            if appointment_shows_in_calendar(appointment)
        ),
        key=lambda appointment: (appointment["date"], appointment["time"]),
    )
    return render_template(
        "admin_calendar.html",
        active_page="calendar",
        profile=admin_profile(),
        appointments=appointments,
        created=request.args.get("created") == "1",
        updated=request.args.get("updated") == "1",
        date_unavailable=request.args.get("date_unavailable") == "1",
    )


@app.route("/admin/calendar/<int:appointment_id>/status", methods=["POST"])
def update_appointment_status(appointment_id):
    guard = admin_guard()
    if guard:
        return guard

    appointment = find_appointment(appointment_id)
    new_status = request.form.get("status", "").strip()
    if appointment:
        appointment["status"] = new_status or appointment["status"]
        save_data()

    if (new_status or "").lower() == "cancelled":
        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("admin_calendar", updated="1"))


@app.route("/admin/patients", methods=["GET", "POST"])
def admin_patients():
    guard = admin_guard()
    if guard:
        return guard

    if request.method == "POST":
        PATIENTS.append(
            {
                "id": next_patient_id(),
                "name": request.form["name"].strip(),
                "age": int(request.form["age"]),
                "gender": request.form["gender"].strip(),
                "phone": request.form["phone"].strip(),
                "status": request.form["status"].strip(),
                "condition": request.form["condition"].strip(),
            }
        )
        save_data()
        return redirect(url_for("admin_patients", added="1"))

    query = request.args.get("q", "").strip().lower()
    patients = PATIENTS
    if query:
        patients = [
            patient
            for patient in PATIENTS
            if query in patient["name"].lower()
            or query in patient["phone"].lower()
            or query in patient["condition"].lower()
        ]

    patient_emails = {}
    for appointment in sorted(
        APPOINTMENTS,
        key=lambda item: (item.get("date", ""), item.get("time", "")),
        reverse=True,
    ):
        patient_key = normalize_patient_name(appointment.get("patient", ""))
        appointment_email = (appointment.get("email") or "").strip()
        if patient_key and appointment_email and patient_key not in patient_emails:
            patient_emails[patient_key] = appointment_email

    user_email_lookup = fetch_user_email_lookup()

    patient_email_by_id = {}
    for patient in patients:
        patient_key = normalize_patient_name(patient.get("name", ""))
        patient_email_by_id[patient["id"]] = (
            patient_emails.get(patient_key, "")
            or user_email_lookup.get(patient_key, "")
        )

    return render_template(
        "admin_patients.html",
        active_page="patients",
        profile=admin_profile(),
        patients=patients,
        patient_email_by_id=patient_email_by_id,
        patient_histories={
            patient["id"]: build_patient_history(patient) for patient in patients
        },
        search_query=request.args.get("q", ""),
        added=request.args.get("added") == "1",
    )


@app.route("/admin/patients/<int:patient_id>")
def admin_patient_history(patient_id):
    guard = admin_guard()
    if guard:
        return guard

    return redirect(url_for("admin_patients"))


@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    guard = admin_guard()
    if guard:
        return guard

    account_username = admin_account_key()

    if request.method == "POST":
        display_name = request.form["display_name"].strip() or session.get(
            "username", "Admin User"
        )
        email = request.form["email"].strip() or session.get(
            "email", "admin@schedtalk.com"
        )
        clinic_name = request.form["clinic_name"].strip() or "SchedTalk Clinic"
        contact_number = request.form["contact_number"].strip() or "+63 912 000 0000"
        profile_image_path = session.get("profile_pic", "")
        image_file = request.files.get("profile_image")

        if image_file and image_file.filename:
            try:
                profile_image_path = save_admin_profile_image(account_username, image_file)
            except ValueError as error:
                return redirect(url_for("admin_settings", upload_error=str(error)))

        persist_admin_profile(
            account_username,
            {
                "display_name": display_name,
                "email": email,
                "clinic_name": clinic_name,
                "contact_number": contact_number,
                "profile_image": profile_image_path,
            },
        )
        apply_admin_profile_to_session(account_username)
        return redirect(url_for("admin_settings", saved="1"))

    return render_template(
        "admin_settings.html",
        active_page="settings",
        profile=admin_profile(),
        clinic_name=session.get("clinic_name", "SchedTalk Clinic"),
        contact_number=session.get("contact_number", "+63 912 000 0000"),
        saved=request.args.get("saved") == "1",
        upload_error=request.args.get("upload_error", ""),
    )


@app.route("/signup", methods=["POST"])
def signup():
    if request.method == "POST":
        ensure_user_profile_columns()

        fname = request.form["firstname"]
        lname = request.form["lastname"]
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        phone = request.form["phone"].strip()
        age = request.form["age"].strip()
        gender = request.form["gender"].strip()

        full_name = " ".join(part for part in [fname.strip(), lname.strip()] if part)

        if fetch_user_by_username(username):
            return redirect(
                url_for(
                    "index",
                    signup_error="Username already used.",
                    signup_firstname=fname,
                    signup_lastname=lname,
                    signup_username=username,
                    signup_email=email,
                    signup_phone=phone,
                    signup_age=age,
                    signup_gender=gender,
                )
            )

        if fetch_user_by_email(email):
            return redirect(
                url_for(
                    "index",
                    signup_error="Email already registered.",
                    signup_firstname=fname,
                    signup_lastname=lname,
                    signup_username=username,
                    signup_email=email,
                    signup_phone=phone,
                    signup_age=age,
                    signup_gender=gender,
                )
            )

        cur = mysql.connection.cursor()
        cur.execute(
            """
            INSERT INTO users (username, password, email, role, full_name, phone, age, gender)
            VALUES (%s, %s, %s, 'user', %s, %s, %s, %s)
            """,
            (username, generate_password_hash(password), email, full_name, phone, int(age), gender),
        )
        mysql.connection.commit()
        cur.close()

        session["full_name"] = full_name
        session["phone"] = phone
        session["age"] = int(age)
        session["gender"] = gender
        session["email"] = email

        return redirect(url_for("index", signup_success="1", signup_username=username))


@app.route("/signup", methods=["GET"])
def signup_get():
    return redirect(url_for("index"))


@app.route("/login", methods=["POST"])
def login():
    if request.method == "POST":
        ensure_user_profile_columns()
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        user = fetch_user_by_username(username)

        if user:
            if not verify_password(user[2], password):
                return redirect(
                    url_for(
                        "index",
                        login_error="wrong_password",
                        username=username,
                    )
                )

            return begin_otp_for_user(user, username)

        return redirect(
            url_for(
                "index",
                login_error="user_not_found",
                username=username,
            )
        )


@app.route("/login", methods=["GET"])
def login_get():
    return redirect(url_for("index"))


@app.route("/auth/google")
def google_auth_start():
    client_id = app.config["GOOGLE_CLIENT_ID"]
    if not client_id:
        return redirect(url_for("index", login_error="google_not_configured"))

    redirect_uri = app.config["GOOGLE_REDIRECT_URI"] or url_for("google_auth_callback", _external=True)
    state = uuid4().hex
    session["google_oauth_state"] = state

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@app.route("/auth/google/callback")
def google_auth_callback():
    state = request.args.get("state", "")
    code = request.args.get("code", "")

    if not state or state != session.get("google_oauth_state"):
        return redirect(url_for("index", login_error="google_state_mismatch"))
    session.pop("google_oauth_state", None)

    if not code:
        return redirect(url_for("index", login_error="google_login_failed"))

    client_id = app.config["GOOGLE_CLIENT_ID"]
    client_secret = app.config["GOOGLE_CLIENT_SECRET"]
    redirect_uri = app.config["GOOGLE_REDIRECT_URI"] or url_for("google_auth_callback", _external=True)

    if not client_id or not client_secret:
        return redirect(url_for("index", login_error="google_not_configured"))

    token_payload = urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    try:
        token_request = Request(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(token_request, timeout=10) as token_response:
            token_data = json.loads(token_response.read().decode("utf-8"))

        access_token = token_data.get("access_token", "")
        if not access_token:
            return redirect(url_for("index", login_error="google_login_failed"))

        userinfo_request = Request(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        with urlopen(userinfo_request, timeout=10) as userinfo_response:
            userinfo = json.loads(userinfo_response.read().decode("utf-8"))
    except Exception:
        return redirect(url_for("index", login_error="google_login_failed"))

    email = (userinfo.get("email") or "").strip().lower()
    if not email:
        return redirect(url_for("index", login_error="google_login_failed"))

    ensure_user_profile_columns()
    user = fetch_user_by_email(email)
    if not user:
        display_name = (userinfo.get("name") or email.split("@")[0]).strip()
        username = make_unique_username(email.split("@")[0])

        cur = mysql.connection.cursor()
        cur.execute(
            """
            INSERT INTO users (username, password, email, role, full_name, phone, age, gender)
            VALUES (%s, %s, %s, 'user', %s, %s, %s, %s)
            """,
            (username, generate_password_hash(uuid4().hex), email, display_name, "", 18, "Other"),
        )
        mysql.connection.commit()
        cur.close()
        user = fetch_user_by_email(email)

    if not user:
        return redirect(url_for("index", login_error="google_login_failed"))

    return begin_otp_for_user(user, user[1])


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "pending_otp_hash" not in session or "pending_user" not in session:
        return redirect(url_for("index"))

    if request.method == "GET":
        return redirect(url_for("index", otp_required="1"))

    if request.method == "POST":
        user_otp = request.form.get("otp", "").strip()

        if time.time() > session.get("pending_otp_expiry", 0):
            session.pop("pending_otp_hash", None)
            session.pop("pending_otp_expiry", None)
            session.pop("pending_otp_attempts", None)
            session.pop("pending_user", None)
            return redirect(url_for("index", login_error="otp_expired"))

        session["pending_otp_attempts"] = session.get("pending_otp_attempts", 0) + 1
        if session["pending_otp_attempts"] > 5:
            session.pop("pending_otp_hash", None)
            session.pop("pending_otp_expiry", None)
            session.pop("pending_otp_attempts", None)
            session.pop("pending_user", None)
            return redirect(url_for("index", login_error="otp_too_many"))

        if hash_text(user_otp) == session.get("pending_otp_hash"):
            pending_user = session.get("pending_user", {})

            session["loggedin"] = True
            session["account_username"] = pending_user.get("account_username", "")
            session["username"] = pending_user.get("username", "")
            session["email"] = pending_user.get("email", "")
            session["profile_pic"] = ""
            session["role"] = pending_user.get("role", "user")
            session["full_name"] = pending_user.get("full_name", session.get("username", ""))
            session["phone"] = pending_user.get("phone", "")
            session["age"] = pending_user.get("age")
            session["gender"] = pending_user.get("gender", "")

            session.pop("pending_otp_hash", None)
            session.pop("pending_otp_expiry", None)
            session.pop("pending_otp_attempts", None)
            session.pop("pending_user", None)

            if session["role"] == "admin":
                apply_admin_profile_to_session(
                    session["username"],
                    default_username=session["username"],
                    default_email=session["email"],
                )
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))

        return redirect(url_for("index", otp_required="1", otp_error="invalid"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
