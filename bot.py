
import os
import requests
import schedule
import time
import telebot
from dotenv import load_dotenv
from keep_alive import keep_alive

# بارگذاری متغیرهای محیطی
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002250994558"))

if not BOT_TOKEN:
    raise ValueError("توکن ربات یافت نشد!")

bot = telebot.TeleBot(BOT_TOKEN)
keep_alive()

# دریافت قیمت طلا از TwelveData
def fetch_gold_data():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "XAU/USD",
        "interval": "5min",
        "outputsize": 30,
        "apikey": "30e73a1373474b43912716946c754e08"
    }
    return requests.get(url, params=params).json()

# تحلیل تکنیکال با MACD و RSI
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

        if rsi < 30 and macd_line[-1] > signal_line[-1]:
            return "buy"
        elif rsi > 70 and macd_line[-1] < signal_line[-1]:
            return "sell"
        else:
            return None
    except:
        return None

# دریافت اخبار اقتصادی از TwelveData
def fetch_economic_news():
    url = "https://api.twelvedata.com/news"
    params = {
        "symbol": "XAU/USD",
        "apikey": "30e73a1373474b43912716946c754e08"
    }
    try:
        res = requests.get(url, params=params).json()
        headlines = [item['title'] for item in res.get('data', [])[:5]]
        return headlines
    except:
        return []

# ارسال پیام به کانال
def send_to_channel(text):
    try:
        bot.send_message(CHANNEL_ID, text)
        print("✅ پیام ارسال شد.")
    except Exception as e:
        print(f"❌ ارسال ناموفق: {e}")

# تحلیل کامل بازار و اخبار
def main_job():
    print("📊 تحلیل بازار در حال اجرا...")
    data = fetch_gold_data()
    signal = analyze_signal(data)
    if signal:
        msg = "📈 سیگنال خرید قوی!" if signal == "buy" else "📉 سیگنال فروش قوی!"
        send_to_channel(msg)
    else:
        print("⏳ سیگنالی صادر نشد.")

    news = fetch_economic_news()
    if news:
        send_to_channel("📰 آخرین اخبار اقتصادی:")
        for n in news:
            send_to_channel(f"🟡 {n}")

# پاسخ به دستور /status
@bot.message_handler(commands=['status'])
def status(message):
    bot.reply_to(message, "✅ ربات آنلاین است و تحلیل انجام می‌دهد.")

# دریافت همه پیام‌ها (برای لاگ‌گیری)
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    print(f"📨 پیام دریافت شد: {message.text}")

# اجرای خودکار هر ۱۵ دقیقه
schedule.every(15).minutes.do(main_job)

# شروع برنامه
print("🤖 ربات تحلیل‌گر طلا فعال شد...")
while True:
    schedule.run_pending()
    time.sleep(1)
