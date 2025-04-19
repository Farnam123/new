import os
import time
import requests
import schedule
import telebot
import numpy as np
import pandas as pd
from flask import Flask, request
from threading import Thread
from dotenv import load_dotenv
from transformers import pipeline

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "110251199"))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
sentiment_analyzer = pipeline("sentiment-analysis")

# تحلیل اخبار
def fetch_news_sentiment():
    try:
        url = f"https://newsapi.org/v2/top-headlines?q=gold+usd+inflation&language=en&apiKey={NEWSAPI_KEY}"
        res = requests.get(url)
        news = res.json().get("articles", [])[:3]
        return [(n["title"], sentiment_analyzer(n["title"])[0]['score']) for n in news]
    except:
        return []

# داده‌های تکنیکال
def fetch_technical_data():
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=50&apikey={TWELVEDATA_API_KEY}"
    res = requests.get(url)
    data = res.json().get("values", [])
    return [float(x["close"]) for x in reversed(data)] if data else []

def calculate_macd(closes):
    short_ema = pd.Series(closes).ewm(span=12, adjust=False).mean()
    long_ema = pd.Series(closes).ewm(span=26, adjust=False).mean()
    macd = short_ema - long_ema
    signal = macd.ewm(span=9, adjust=False).mean()
    if len(macd) < 2 or len(signal) < 2:
        return "neutral"
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
    if avg_loss == 0:
        return "neutral"
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    if rsi < 30:
        return "oversold"
    elif rsi > 70:
        return "overbought"
    return "neutral"

def calculate_signal_score(macd_sig, rsi_sig, news_sentiments):
    score = 0
    if macd_sig == "bullish": score += 30
    elif macd_sig == "bearish": score -= 30

    if rsi_sig == "oversold": score += 25
    elif rsi_sig == "overbought": score -= 25

    news_score = sum([s for _, s in news_sentiments])
    score += int(news_score * 25)

    return min(max(score, 0), 100)

def send_to_channel(text):
    try:
        bot.send_message(ADMIN_ID, text)
    except Exception as e:
        print(f"❌ ارسال ناموفق: {e}")

# تحلیل اصلی
def main_job():
    try:
        closes = fetch_technical_data()
        if len(closes) < 30:
            send_to_channel("⚠️ داده‌های کافی برای تحلیل دریافت نشد.")
            return

        macd_sig = calculate_macd(closes)
        rsi_sig = calculate_rsi(closes)
        news = fetch_news_sentiment()
        score = calculate_signal_score(macd_sig, rsi_sig, news)

        if score >= 70:
            msg = f"""📊 سیگنال خرید قوی!
💡 امتیاز: {score}/100
🔧 MACD: {macd_sig}
📈 RSI: {rsi_sig}
📰 اخبار:\n""" + "\n".join([f"• {t} ({round(s,2)})" for t, s in news])
            send_to_channel(msg)
        else:
            send_to_channel(f"⏳ سیگنال صادر نشد. امتیاز: {score}/100")

    except Exception as e:
        send_to_channel(f"❌ خطا در تحلیل: {e}")

# Webhook endpoint
@app.route(f"/{TOKEN}", methods=['POST'])
def telegram_webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return 'ok', 200

@app.route("/")
def home():
    return "Bot is alive!"

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام فرنام! ربات Webhook با تحلیل فعال شد ✅")

@bot.message_handler(commands=['signal'])
def manual_signal(message):
    bot.reply_to(message, "در حال اجرای تحلیل دستی...")
    main_job()

# Webhook setup
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{APP_URL}/{TOKEN}")
    Thread(target=lambda: schedule.every(5).minutes.do(main_job)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
