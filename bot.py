
import os
import sqlite3
import requests
import schedule
import time
import telebot
from dotenv import load_dotenv
from keep_alive import keep_alive
from datetime import datetime

# بارگذاری توکن
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002250994558"))
bot = telebot.TeleBot(BOT_TOKEN)
keep_alive()

# راه‌اندازی دیتابیس
conn = sqlite3.connect("signals.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS signals
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              type TEXT,
              message TEXT,
              created_at TEXT)''')
conn.commit()

def log_signal(sig_type, msg):
    c.execute("INSERT INTO signals (type, message, created_at) VALUES (?, ?, ?)",
              (sig_type, msg, datetime.now().isoformat()))
    conn.commit()

def fetch_gold_data():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "XAU/USD",
        "interval": "5min",
        "outputsize": 30,
        "apikey": "30e73a1373474b43912716946c754e08"
    }
    return requests.get(url, params=params).json()

def analyze_signal(data):
    try:
        closes = [float(c['close']) for c in data['values']][::-1]
        if len(closes) < 26: return None

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

        if rsi < 30 and macd_line[-1] > signal_line[-1]:
            return "buy"
        elif rsi > 70 and macd_line[-1] < signal_line[-1]:
            return "sell"
        else:
            return None
    except:
        return None

def fetch_economic_news():
    url = "https://api.twelvedata.com/news"
    params = {
        "symbol": "XAU/USD",
        "apikey": "30e73a1373474b43912716946c754e08"
    }
    try:
        res = requests.get(url, params=params).json()
        return [item['title'] for item in res.get('data', [])[:5]]
    except:
        return []

def send_to_channel(text):
    try:
        bot.send_message(CHANNEL_ID, text)
        print("✅ پیام ارسال شد.")
    except Exception as e:
        print(f"❌ ارسال ناموفق: {e}")

def main_job():
    print("🔍 بررسی سیگنال‌ها...")
    data = fetch_gold_data()
    signal = analyze_signal(data)
    if signal:
        msg = "📈 سیگنال خرید قوی!" if signal == "buy" else "📉 سیگنال فروش قوی!"
        send_to_channel(msg)
        log_signal(signal, msg)
    else:
        print("⏳ سیگنالی صادر نشد.")

    news = fetch_economic_news()
    if news:
        send_to_channel("📰 آخرین اخبار اقتصادی:")
        for n in news:
            send_to_channel(f"🟡 {n}")
            log_signal("news", n)

@bot.message_handler(commands=['status'])
def status(message):
    bot.reply_to(message, "✅ ربات فعال است.")

@bot.message_handler(commands=['history'])
def history(message):
    c.execute("SELECT type, message, created_at FROM signals ORDER BY id DESC LIMIT 10")
    records = c.fetchall()
    if records:
        response = "

".join([f"{r[2]} | {r[0]}:
{r[1]}" for r in records])
    else:
        response = "هیچ سیگنالی هنوز ثبت نشده."
    bot.reply_to(message, response)

@bot.message_handler(commands=['export'])
def export_csv(message):
    path = "/tmp/signals_export.csv"
    with open(path, "w") as f:
        f.write("Type,Message,Created_At
")
        for row in c.execute("SELECT type, message, created_at FROM signals"):
            f.write(f"{row[0]},{row[1].replace(',', ';')},{row[2]}
")
    with open(path, "rb") as f:
        bot.send_document(message.chat.id, f)

schedule.every(15).minutes.do(main_job)

print("🤖 ربات تحلیل‌گر طلا فعال شد...")
while True:
    schedule.run_pending()
    time.sleep(1)
