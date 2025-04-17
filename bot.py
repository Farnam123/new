import os
import sqlite3
import requests
import schedule
import time
import telebot
import threading
from dotenv import load_dotenv
from datetime import datetime
from keep_alive import keep_alive

# بارگذاری متغیرهای محیطی
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002250994558"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "110251199"))

if not BOT_TOKEN:
    raise ValueError("توکن ربات یافت نشد!")

bot = telebot.TeleBot(BOT_TOKEN)
keep_alive()

# راه‌اندازی دیتابیس SQLite
conn = sqlite3.connect("signals.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS signals
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              type TEXT,
              message TEXT,
              score INTEGER,
              created_at TEXT)''')
conn.commit()

# لاگ سیگنال در دیتابیس
def log_signal(sig_type, msg, score):
    c.execute("INSERT INTO signals (type, message, score, created_at) VALUES (?, ?, ?, ?)",
              (sig_type, msg, score, datetime.now().isoformat()))
    conn.commit()

# دریافت داده طلا
def fetch_gold_data(interval="5min"):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "XAU/USD",
        "interval": interval,
        "outputsize": 30,
        "apikey": "30e73a1373474b43912716946c754e08"
    }
    return requests.get(url, params=params).json()

# تحلیل با MACD و RSI
def analyze_signal(data):
    try:
        closes = [float(c['close']) for c in data['values']][::-1]
        if len(closes) < 26:
            return None

        def ema(prices, p):
            ema_vals = [sum(prices[:p]) / p]
            k = 2 / (p + 1)
            for price in prices[p:]:
                ema_vals.append(price * k + ema_vals[-1] * (1 - k))
            return ema_vals

        ema_12 = ema(closes, 12)
        ema_26 = ema(closes, 26)
        macd_line = [a - b for a, b in zip(ema_12[-len(ema_26):], ema_26)]
        signal_line = ema(macd_line, 9)

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))

        signal = None
        score = 0
        if rsi < 30 and macd_line[-1] > signal_line[-1]:
            signal = "buy"
            score += 1
        elif rsi > 70 and macd_line[-1] < signal_line[-1]:
            signal = "sell"
            score += 1

        return (signal, score)
    except:
        return None

# ارسال پیام به کانال و ادمین
def send_to_channel(text):
    try:
        bot.send_message(CHANNEL_ID, text)
        bot.send_message(ADMIN_ID, f"📬 نوتیفیکیشن: {text}")
        print("✅ پیام ارسال شد.")
    except Exception as e:
        print(f"❌ ارسال ناموفق: {e}")

# اجرای تحلیل اصلی
def main_job():
    print("🔍 تحلیل بازار در حال اجرا...")
    result_5m = analyze_signal(fetch_gold_data("5min"))
    result_15m = analyze_signal(fetch_gold_data("15min"))

    if result_5m and result_15m:
        sig1, score1 = result_5m
        sig2, score2 = result_15m
        if sig1 == sig2 and sig1 is not None:
            total_score = score1 + score2 + 1
            msg = f"{'📈' if sig1=='buy' else '📉'} سیگنال {sig1.upper()} قوی!\nامتیاز: {total_score}/5"
            send_to_channel(msg)
            log_signal(sig1, msg, total_score)
        else:
            print("❕ سیگنال‌ها متفاوت بودن یا نامشخص.")
    else:
        print("⏳ اطلاعات ناکافی برای تحلیل.")

# دستور وضعیت
@bot.message_handler(commands=['status'])
def status(message):
    bot.reply_to(message, "✅ ربات آنلاین است و تحلیل ترکیبی انجام می‌دهد.")

# تاریخچه سیگنال
@bot.message_handler(commands=['history'])
def history(message):
    c.execute("SELECT type, message, score, created_at FROM signals ORDER BY id DESC LIMIT 10")
    records = c.fetchall()
    if records:
        response = "\n\n".join([f"{r[3]} | {r[0]} (امتیاز {r[2]}):\n{r[1]}" for r in records])
    else:
        response = "📭 هنوز سیگنالی ثبت نشده."
    bot.reply_to(message, response)

# خروجی CSV
@bot.message_handler(commands=['export'])
def export_csv(message):
    path = "/tmp/signals_export.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write("Type,Message,Score,Created_At\n")
        for row in c.execute("SELECT type, message, score, created_at FROM signals"):
            f.write(f"{row[0]},{row[1].replace(',', ';')},{row[2]},{row[3]}\n")
    with open(path, "rb") as f:
        bot.send_document(message.chat.id, f)

# راه‌اندازی polling به‌صورت thread
def start_polling():
    print("🤖 ربات تلگرام در حال اجرا...")
    bot.infinity_polling(timeout=60, long_polling_timeout=20)

# اجرای برنامه اصلی
if __name__ == "__main__":
    # اجرای threading برای بات
    threading.Thread(target=start_polling).start()

    # اجرای تحلیل طبق زمان‌بندی
    schedule.every(15).minutes.do(main_job)
    print("📈 اجرای تحلیل زمان‌بندی‌شده شروع شد...")

    while True:
        schedule.run_pending()
        time.sleep(1)
