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
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not BOT_TOKEN:
    raise ValueError("توکن ربات یافت نشد!")

bot = telebot.TeleBot(BOT_TOKEN)
keep_alive()

# راه‌اندازی دیتابیس
conn = sqlite3.connect("signals.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS signals
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              type TEXT,
              message TEXT,
              score INTEGER,
              created_at TEXT)''')
conn.commit()

# ذخیره سیگنال
def log_signal(sig_type, msg, score):
    c.execute("INSERT INTO signals (type, message, score, created_at) VALUES (?, ?, ?, ?)",
              (sig_type, msg, score, datetime.now().isoformat()))
    conn.commit()

# دریافت قیمت طلا
def fetch_gold_data(interval="5min"):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "XAU/USD",
        "interval": interval,
        "outputsize": 30,
        "apikey": "30e73a1373474b43912716946c754e08"
    }
    return requests.get(url, params=params).json()

# تحلیل MACD و RSI
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

# تحلیل فیبوناچی ساده
def check_fibonacci_signal(data):
    try:
        prices = [float(c['close']) for c in data['values']][::-1]
        recent_high = max(prices[-10:])
        recent_low = min(prices[-10:])
        last_price = prices[-1]
        fib_382 = recent_high - 0.382 * (recent_high - recent_low)
        fib_618 = recent_high - 0.618 * (recent_high - recent_low)

        if abs(last_price - fib_382) < 1 or abs(last_price - fib_618) < 1:
            return 1
        return 0
    except:
        return 0

# تحلیل فرکتال ساده
def check_fractal_signal(data):
    try:
        highs = [float(x['high']) for x in data['values']][::-1]
        lows = [float(x['low']) for x in data['values']][::-1]
        if highs[2] > highs[1] and highs[2] > highs[3]:
            return 1  # سیگنال فروش
        if lows[2] < lows[1] and lows[2] < lows[3]:
            return 1  # سیگنال خرید
        return 0
    except:
        return 0

# تحلیل احساسات از NewsAPI
def fetch_news_sentiment():
    try:
        url = f"https://newsapi.org/v2/everything?q=gold+XAUUSD&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
        res = requests.get(url).json()
        titles = [article['title'] for article in res['articles'][:5]]
        positives = sum(1 for t in titles if any(w in t.lower() for w in ["up", "rise", "bullish", "gain"]))
        negatives = sum(1 for t in titles if any(w in t.lower() for w in ["down", "drop", "bearish", "fall"]))
        if positives > negatives:
            return 1
        elif negatives > positives:
            return -1
        return 0
    except:
        return 0

# تحلیل ترکیبی هوشمند
def smart_analysis():
    try:
        data_5m = fetch_gold_data("5min")
        data_15m = fetch_gold_data("15min")
        news_score = fetch_news_sentiment()
        fib_score = check_fibonacci_signal(data_5m)
        fractal_score = check_fractal_signal(data_5m)

        score = 0
        signal_final = None

        sig_5m = analyze_signal(data_5m)
        sig_15m = analyze_signal(data_15m)

        if sig_5m and sig_15m and sig_5m[0] == sig_15m[0] and sig_5m[0] is not None:
            signal_final = sig_5m[0]
            score += sig_5m[1] + sig_15m[1] + 1
        else:
            return None

        score += fib_score + fractal_score
        if news_score == 1:
            score += 1

        return (signal_final, score)
    except Exception as e:
        print(f"❌ خطا در تحلیل نهایی: {e}")
        return None

# ارسال پیام
def send_to_channel(text):
    try:
        bot.send_message(CHANNEL_ID, text)
        bot.send_message(ADMIN_ID, f"📬 نوتیفیکیشن: {text}")
        print("✅ پیام ارسال شد.")
    except Exception as e:
        print(f"❌ ارسال ناموفق: {e}")

# اجرای اصلی
def main_job():
    print("🚀 تحلیل ترکیبی در حال اجرا...")
    result = smart_analysis()
    if result:
        signal, score = result
        msg = f"{'📈' if signal == 'buy' else '📉'} سیگنال {signal.upper()} هوشمند 🔍\nامتیاز: {score}/5"
        send_to_channel(msg)
        log_signal(signal, msg, score)
    else:
        print("⏳ سیگنالی صادر نشد.")

# فرمان‌ها
@bot.message_handler(commands=['status'])
def status(message):
    bot.reply_to(message, "✅ ربات آنلاین است و تحلیل ترکیبی انجام می‌دهد.")

@bot.message_handler(commands=['history'])
def history(message):
    c.execute("SELECT type, message, score, created_at FROM signals ORDER BY id DESC LIMIT 10")
    records = c.fetchall()
    if records:
        response = "\n\n".join([f"{r[3]} | {r[0]} (امتیاز {r[2]}):\n{r[1]}" for r in records])
    else:
        response = "📭 هنوز سیگنالی ثبت نشده."
    bot.reply_to(message, response)

@bot.message_handler(commands=['export'])
def export_csv(message):
    path = "/tmp/signals.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write("Type,Message,Score,Created_At\n")
        for row in c.execute("SELECT type, message, score, created_at FROM signals"):
            f.write(f"{row[0]},{row[1].replace(',', ';')},{row[2]},{row[3]}\n")
    with open(path, "rb") as f:
        bot.send_document(message.chat.id, f)

# اجرا
def start_polling():
    bot.infinity_polling(timeout=60, long_polling_timeout=20)

if __name__ == "__main__":
    threading.Thread(target=start_polling).start()
    schedule.every(15).minutes.do(main_job)
    print("📈 تحلیل‌گر طلا در حال اجراست...")
    while True:
        schedule.run_pending()
        time.sleep(1)
