# ⚡ HyperTask AI

> **Automated, Real-Time Task Scheduling Engine with Instant Telegram Alerts.**

HyperTask AI is a lightweight, full-stack scheduling application featuring a modern cyberpunk glassmorphism interface, robust local authentication, and an asynchronous background scheduler that dispatches instant reminders directly to your smartphone via the Telegram Bot API.

---

## ✨ Features

- **🔐 User Authentication:** Secure signup and login flow powered by hashed passwords.
- **🎨 Modern Dark/Glassmorphic UI:** Clean, responsive design featuring glowing gradient aesthetics and dynamic status badges.
- **⏰ Real-Time Background Scheduler:** Continuous task monitoring powered by `APScheduler` without manual page refreshes.
- **📲 Telegram Push Alerts:** Free, instant notifications sent directly to your phone via custom Telegram bots.
- **🗃️ Lightweight Database:** Powered by SQLite with SQLAlchemy ORM for zero-configuration setup.

---

## 🛠️ Tech Stack

- **Frontend:** HTML5, CSS3 (Glassmorphism), Vanilla JavaScript (Fetch API)
- **Backend:** Python (Flask, Flask-SQLAlchemy)
- **Background Engine:** APScheduler
- **Notification Pipeline:** Telegram Bot API
- **Database:** SQLite

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+ installed on your system.
- A Telegram account to create your notification bot.

---

### 1. Set Up Your Telegram Bot

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts to create your bot.
3. Save the **HTTP API Token** provided.
4. Search for `@userinfobot` on Telegram to retrieve your **Telegram Chat ID**.

---

