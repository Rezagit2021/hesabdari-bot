from flask import Flask
import os
import subprocess
import sys
import threading
import time
import requests

app = Flask(__name__)
TOKEN = '8678842471:AAGg09zAWG7xC2vdzVE4-0iTDaW73QUwuwc'


@app.route('/')
def home():
    return "ربات حسابداری فعال است 🤖"


@app.route('/health')
def health():
    return "OK", 200


def start_bot():
    """اجرای ربات در یک فرآیند جداگانه"""
    try:
        print("🚀 شروع فرآیند ربات...")
        # پاک کردن webhook قبل از شروع
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
        print("✅ Webhook پاک شد")

        # اجرای main.py به عنوان یک فرآیند جدا
        process = subprocess.Popen([sys.executable, "main.py"])
        print("✅ ربات در فرآیند جداگانه اجرا شد (PID: {})".format(process.pid))
    except Exception as e:
        print(f"❌ خطا در اجرای ربات: {e}")


def keep_alive():
    """هر ۵ دقیقه یه بار به تلگرام پینگ می‌زنیم"""
    while True:
        time.sleep(300)  # ۵ دقیقه
        try:
            requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe")
            print("💓 پینگ زده شد - ربات فعال است")
        except Exception as e:
            print(f"⚠️ خطا در پینگ: {e}")


# شروع ربات
start_bot()

# راه‌اندازی ترد جداگانه برای پینگ
ping_thread = threading.Thread(target=keep_alive)
ping_thread.daemon = True
ping_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)