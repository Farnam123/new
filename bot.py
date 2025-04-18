import os
import time
import requests
import schedule
import telebot
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from threading import Thread
from transformers import pipeline

# بارگذاری متغیرها
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
USDT_ADDRESS = os.getenv("USDT_ADDRESS")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "110251199"))

bot = telebot.TeleBot(TOKEN, threaded=False)
sentiment_analyzer = pipeline("sentiment-analysis")

# تحلیل اخبار
def fetch_news_sentiment():
    url = f"https://newsapi.org/v2/top-headlines?q=gold+usd+inflation&language=en&apiKey={NEWSAPI_KEY}"
    res = requests.get(url)
    if res.status_code != 200:
        return []
    news = res.json().get("articles", [])[:3]
    scored_news = []
    for article in news:
        title = article["title"]
        sentiment = sentiment_analyzer(title)[0]
        score = sentiment['score'] if sentiment['label'] == 'POSITIVE' else -sentiment['score']
        scored_news.append((title, score))
    return scored_news

# تحلیل تکنیکال
def fetch_technical_data():
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=50&apikey={TWELVEDATA_API_KEY}"
    res = requests.get(url)
    data = res.json().get("values", [])
    closes = [float(x["close"]) for x in reversed(data)]
    return closes

def calculate_macd(closes):
    short_ema = pd.Series(closes).ewm(span=12, adjust=False).mean()
    long_ema = pd.Series(closes).ewm(span=26, adjust=False).mean()
    macd = short_ema - long_ema
    signal = macd.ewm(span=9, adjust=False).mean()
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        return "bullish"
    elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        return "bearish"
    return "neutral"

def calculate_rsi(closes, period=14):
    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    if rsi < 30:
        return "oversold"
    elif rsi > 70:
        return "overbought"
    return "neutral"

# امتیازدهی
def calculate_signal_score(macd_sig, rsi_sig, news_sentiments):
    score = 0
    if macd_sig == "bullish":
        score += 30
    elif macd_sig == "bearish":
        score -= 30

    if rsi_sig == "oversold":
        score += 25
    elif rsi_sig == "overbought":
        score -= 25

    news_score = sum([s for _, s in news_sentiments])
    score += int(news_score * 25)

    return min(max(score, 0), 100)

# ارسال به چت
def send_to_channel(text):
    try:
        bot.send_message(ADMIN_ID, text)
    except Exception as e:
        print(f"❌ خطا در ارسال: {e}")

# تحلیل اصلی
def main_job():
    try:
        send_to_channel("🔍 تحلیل جدید شروع شد...")

        closes = fetch_technical_data()
        macd_sig = calculate_macd(closes)
        rsi_sig = calculate_rsi(closes)
        news = fetch_news_sentiment()

        score = calculate_signal_score(macd_sig, rsi_sig, news)

        if score >= 70:
            msg = f"""📊 سیگنال خرید قوی!
💡 امتیاز: {score}/100
🔧 MACD: {macd_sig}
📈 RSI: {rsi_sig}
📰 اخبار:
""" + "\n".join([f"• {t} ({round(s,2)})" for t, s in news])
            send_to_channel(msg)
        else:
            send_to_channel(f"⏳ امتیاز سیگنال پایین بود ({score}/100) - سیگنال ارسال نشد.")

    except Exception as e:
        send_to_channel(f"❌ خطا در تحلیل: {e}")

# فرمان دستی
@bot.message_handler(commands=['signal'])
def signal_cmd(message):
    bot.reply_to(message, "🚀 اجرای دستی تحلیل بازار...")
    main_job()

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام فرنام! ربات حرفه‌ای فعال شد 🔥")

# اجرای دوره‌ای
schedule.every(5).minutes.do(main_job)

# اجرای پایدار
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# فقط یکبار اجرا
Thread(target=run_scheduler).start()
bot.infinity_polling()
