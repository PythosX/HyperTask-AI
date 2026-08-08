import os
import datetime
import requests
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hypertask_default_secret_key")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///schedule_ai.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Telegram Bot Token (Replace via environment variable or string)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

def send_telegram_alert(chat_id, task_title, schedule_time):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = f"⏰ *HYPERTASK AI ALERT*\n\n📌 *Task:* {task_title}\n🕒 *Time:* {schedule_time}"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending alert: {e}")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    telegram_id = db.Column(db.String(50), nullable=False)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    remind_at = db.Column(db.String(50), nullable=False)
    is_sent = db.Column(db.Boolean, default=False)

def process_due_reminders():
    with app.app_context():
        current_now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
        due_tasks = Schedule.query.filter(Schedule.remind_at <= current_now, Schedule.is_sent == False).all()
        for task in due_tasks:
            user = User.query.get(task.user_id)
            if user:
                send_telegram_alert(user.telegram_id, task.title, task.remind_at)
            task.is_sent = True
            db.session.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(func=process_due_reminders, trigger="interval", seconds=15)
scheduler.start()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    hashed_pwd = generate_password_hash(data['password'], method='scrypt')
    new_user = User(username=data['username'], password=hashed_pwd, telegram_id=data['telegram_id'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Account created successfully'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        session['user_id'] = user.id
        session['username'] = user.username
        return jsonify({'success': True, 'username': user.username})
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/schedules', methods=['GET', 'POST'])
def handle_schedules():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'POST':
        data = request.get_json()
        new_schedule = Schedule(user_id=session['user_id'], title=data['title'], remind_at=data['remind_at'])
        db.session.add(new_schedule)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Schedule saved!'})

    schedules = Schedule.query.filter_by(user_id=session['user_id']).all()
    tasks = [{'id': s.id, 'title': s.title, 'remind_at': s.remind_at, 'is_sent': s.is_sent} for s in schedules]
    return jsonify({'schedules': tasks})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

