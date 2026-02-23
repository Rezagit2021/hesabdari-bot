from flask import Flask
from threading import Thread
import os
import logging
import sys

# اضافه کردن مسیر برای import کردن main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

@app.route('/')
def home():
    return "ربات حسابداری فعال است 🤖"

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    """اجرای ربات اصلی در یک نخ جداگانه"""
    try:
        import main
        # اطمینان از اجرای تابع main
        if hasattr(main, 'main'):
            main.main()
    except Exception as e:
        logging.error(f"خطا در اجرای ربات: {e}")

@app.before_request
def start_bot():
    """شروع ربات قبل از اولین درخواست"""
    if not hasattr(app, 'bot_started'):
        app.bot_started = True
        thread = Thread(target=run_bot)
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)