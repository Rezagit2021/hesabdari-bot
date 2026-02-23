from flask import Flask
from threading import Thread
import os
import logging
import sys
import time

# اضافه کردن مسیر برای import کردن main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flag برای اطمینان از اجرای یک بار ربات
bot_started = False


@app.route('/')
def home():
    return "ربات حسابداری فعال است 🤖"


@app.route('/health')
def health():
    return "OK", 200


def run_bot():
    """اجرای ربات اصلی در یک نخ جداگانه - فقط یک بار"""
    global bot_started
    if bot_started:
        return

    try:
        bot_started = True
        logger.info("ربات در حال راه‌اندازی...")

        # ایمپورت main و اجرای تابع main
        import main
        if hasattr(main, 'main'):
            # اجرا در یک thread جداگانه
            main.main()
        else:
            logger.error("تابع main در فایل main.py یافت نشد!")
    except Exception as e:
        logger.error(f"خطا در اجرای ربات: {e}")
        bot_started = False


# راه‌اندازی ربات در یک thread پس از راه‌اندازی Flask
@app.before_request
def start_bot_once():
    """شروع ربات فقط یک بار"""
    if not bot_started:
        thread = Thread(target=run_bot)
        thread.daemon = True
        thread.start()
        # کمی صبر کن تا ربات شروع به کار کنه
        time.sleep(2)


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)