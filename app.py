from flask import Flask
import os
import subprocess
import sys

app = Flask(__name__)

@app.route('/')
def home():
    return "ربات حسابداری فعال است 🤖"

@app.route('/health')
def health():
    return "OK", 200

def start_bot():
    """اجرای ربات در یک فرآیند جداگانه"""
    try:
        # اجرای main.py به عنوان یک فرآیند جداگانه
        subprocess.Popen([sys.executable, "main.py"])
        print("ربات در فرآیند جداگانه اجرا شد")
    except Exception as e:
        print(f"خطا در اجرای ربات: {e}")

# شروع ربات بعد از راه‌اندازی Flask
start_bot()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)