from flask import Flask
import threading
import os
import logging
import sys
import time

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


def start_bot():
    global bot_started
    if bot_started:
        return

    try:
        bot_started = True
        logger.info("شروع ربات در thread جداگانه...")

        import main
        if hasattr(main, 'main'):
            # main الان فقط thread رو شروع می‌کنه
            main.main()
        else:
            logger.error("تابع main پیدا نشد!")

    except Exception as e:
        logger.error(f"خطا در شروع ربات: {e}")
        bot_started = False


# شروع ربات بعد از راه‌اندازی Flask
with app.app_context():
    thread = threading.Thread(target=start_bot)
    thread.daemon = True
    thread.start()
    time.sleep(3)  # صبر برای شروع ربات

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)