import datetime
import os
from datetime import timedelta
import threading
import time
import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = os.environ.get("SECRET_KEY", "hypertask_default_secret_key")

# Fix Render Postgres URL prefix requirement for SQLAlchemy
db_url = os.environ.get("DATABASE_URL", "sqlite:///schedule_ai.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Make browser sessions last for 30 days
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

db = SQLAlchemy(app)

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE"
)


# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    telegram_id = db.Column(db.String(50), nullable=False)


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    remind_at = db.Column(db.String(50), nullable=False)  # Format: YYYY-MM-DD HH:MM
    is_sent = db.Column(db.Boolean, default=False)


# --- INITIALIZE DATABASE TABLES ---
with app.app_context():
    # UNCOMMENT THE LINE BELOW FOR YOUR FIRST DEPLOYMENT TO FIX TABLE ERRORS, THEN COMMENT IT BACK OUT
    # db.drop_all()
    db.create_all()


# --- TELEGRAM BOT LOGIC ---
def send_telegram_alert(chat_id, task_title, schedule_time):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = f"⏰ *HYPERTASK AI ALERT*\n\n📌 *Task:* {task_title}\n🕒 *Time:* {schedule_time}"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=5)
        print(f"Telegram Alert Sent. Status: {res.status_code}")
        return res.status_code == 200
    except Exception as e:
        print(f"Error sending alert: {e}")
        return False


def send_telegram_start_message(chat_id):
    """Responds to /start with the user's Chat ID for easy signup copy-pasting."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    welcome_text = (
        "⚡ *Welcome to HyperTask AI!*\n\n"
        "I am your automated task reminder assistant.\n\n"
        f"🔑 *Your Telegram Chat ID:* `{chat_id}`\n\n"
        "Copy the Chat ID above and paste it during signup on the web app to pair your account! 🚀"
    )
    payload = {"chat_id": chat_id, "text": welcome_text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error sending start response: {e}")


def poll_telegram_updates():
    """Listens in the background for incoming /start commands on Telegram."""
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 10, "offset": offset}
            res = requests.get(url, params=params, timeout=15)

            if res.status_code == 200:
                data = res.json()
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    message = result.get("message", {})
                    text = message.get("text", "")
                    chat_id = message.get("chat", {}).get("id")

                    if text == "/start" and chat_id:
                        send_telegram_start_message(chat_id)
        except Exception as e:
            print(f"Telegram polling error: {e}")

        time.sleep(2)


# Start Telegram Listener Thread
bot_thread = threading.Thread(target=poll_telegram_updates, daemon=True)
bot_thread.start()


# --- BACKGROUND TASK SCHEDULER ---
def process_due_reminders():
    with app.app_context():
        # Get current time specifically in IST (Asia/Kolkata) matching user inputs
        ist = pytz.timezone("Asia/Kolkata")
        current_now = datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M")

        try:
            due_tasks = Schedule.query.filter(
                Schedule.remind_at <= current_now, Schedule.is_sent == False
            ).all()

            for task in due_tasks:
                user = User.query.get(task.user_id)
                if user and user.telegram_id:
                    sent = send_telegram_alert(
                        user.telegram_id, task.title, task.remind_at
                    )
                    if sent:
                        task.is_sent = True
                        db.session.commit()
                    else:
                        print(f"Failed to deliver message to chat ID: {user.telegram_id}")
        except Exception as e:
            db.session.rollback()
            print(f"Scheduler execution error: {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(func=process_due_reminders, trigger="interval", seconds=15)
scheduler.start()


# --- APP ROUTES ---
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        if (
            not data
            or "username" not in data
            or "password" not in data
            or "telegram_id" not in data
        ):
            return (
                jsonify({"success": False, "message": "Missing required fields"}),
                400,
            )

        if User.query.filter_by(username=data["username"]).first():
            return (
                jsonify({"success": False, "message": "Username already exists"}),
                400,
            )

        hashed_pwd = generate_password_hash(data["password"], method="pbkdf2:sha256")
        new_user = User(
            username=data["username"].strip(),
            password=hashed_pwd,
            telegram_id=str(data["telegram_id"]).strip(),
        )

        db.session.add(new_user)
        db.session.commit()
        return jsonify({"success": True, "message": "Account created successfully"})

    except Exception as e:
        db.session.rollback()
        print(f"Signup Database Error: {e}")
        return jsonify({"success": False, "message": "Server error. Table recreated or invalid data."}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or "username" not in data or "password" not in data:
        return jsonify({"success": False, "message": "Provide credentials"}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if user and check_password_hash(user.password, data["password"]):
        session.permanent = True
        session["user_id"] = user.id
        session["username"] = user.username
        return jsonify({"success": True, "username": user.username})

    return jsonify({"success": False, "message": "Invalid username or password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/schedules", methods=["GET", "POST"])
def handle_schedules():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "POST":
        data = request.get_json()
        # Clean incoming datetime string format to YYYY-MM-DD HH:MM
        remind_time = data["remind_at"].replace("T", " ")

        new_schedule = Schedule(
            user_id=session["user_id"],
            title=data["title"],
            remind_at=remind_time,
        )
        db.session.add(new_schedule)
        db.session.commit()
        return jsonify({"success": True, "message": "Schedule saved!"})

    schedules = Schedule.query.filter_by(user_id=session["user_id"]).all()
    tasks = [
        {
            "id": s.id,
            "title": s.title,
            "remind_at": s.remind_at,
            "is_sent": s.is_sent,
        }
        for s in schedules
    ]
    return jsonify({"schedules": tasks})


if __name__ == "__main__":
    app.run(debug=True)
