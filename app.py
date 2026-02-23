from flask import Flask
import threading
import os
import logging
import sys
import time

# اضافه کردن مسیر برای import کردن main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_started = False


@app.route('/')
def home():
    return "ربات حسابداری فعال است 🤖"


@app.route('/health')
def health():
    return "OK", 200


def run_bot():
    """اجرای ربات اصلی"""
    global bot_started
    if bot_started:
        return

    try:
        bot_started = True
        logger.info("شروع ربات...")

        import main
        # اینجا main.py باید تابع main رو صدا بزنه
        if hasattr(main, 'main'):
            main.main()
        else:
            logger.error("تابع main پیدا نشد!")

    except Exception as e:
        logger.error(f"خطا: {e}")
        bot_started = False


# شروع ربات بعد از راه‌اندازی Flask
with app.app_context():
    thread = threading.Thread(target=run_bot)
    thread.daemon = True
    thread.start()
    time.sleep(2)  # صبر برای شروع ربات

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)