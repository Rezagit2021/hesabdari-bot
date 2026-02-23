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
    """اجرای ربات و ثبت خطاها در فایل"""
    try:
        print("شروع فرآیند ربات...")
        # اجرای main.py و ذخیره خروجی خطا
        with open('bot_errors.log', 'w') as f:
            process = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # خواندن خطاها و چاپ آنها
            stdout, stderr = process.communicate(timeout=5)
            if stdout:
                print("STDOUT:", stdout)
            if stderr:
                print("STDERR:", stderr)
                with open('bot_errors.log', 'a') as log:
                    log.write(stderr)
        print("ربات در فرآیند جداگانه اجرا شد")
    except subprocess.TimeoutExpired:
        # این خطا خوبه! یعنی برنامه هنوز در حال اجراست و timeout خورده
        print("ربات در حال اجراست (timeout expired)")
    except Exception as e:
        print(f"خطا در اجرای ربات: {e}")
        with open('bot_errors.log', 'a') as f:
            f.write(str(e))

# شروع ربات
start_bot()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)