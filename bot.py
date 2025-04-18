import os
import json
import time
import requests
import telebot
import schedule
from flask import Flask, request
from threading import Thread
from datetime import datetime, timedelta
from dotenv import load_dotenv
from transformers import pipeline  # تحلیل احساسات با HuggingFace
import numpy as np

# بارگذاری متغیرهای محیطی
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
REPLIT_PROJECT = os.getenv("REPLIT_PROJECT")
USDT_ADDRESS = os.getenv("USDT_ADDRESS")
ADMIN_ID = int(os.getenv("ADMIN_ID", "110251199"))
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

# پیکربندی ربات
bot = telebot.TeleBot(TOKEN)

# لود مدل تحلیل احساسات
sentiment_analyzer = pipeline("sentiment-analysis")

# دیتابیس کاربران
USERS_FILE = "users.json"

PLANS = {
    "1day": {"price": 3, "days": 1},
    "7days": {"price": 15, "days": 7},
    "30days": {"price": 40, "days": 30}
}

# --- مدیریت کاربران ---
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def is_user_active(user_id):
    users = load_users()
    user = users.get(str(user_id))
    if not user:
        return False
    return datetime.now() < datetime.fromisoformat(user["expire_at"])

def activate_user(user_id, days):
    users = load_users()
    expire_at = datetime.now() + timedelta(days=days)
    users[str(user_id)] = {"expire_at": expire_at.isoformat()}
    save_users(users)

# --- پرداخت و اشتراک ---
@bot.message_handler(commands=['subscribe'])
def show_plans(message):
    text = """پلن‌های اشتراک:
"
    for k, v in PLANS.items():
        text += f"🔹 {k} → {v['price']} USDT / {v['days']} روز\n"
    text += "\nبرای خرید، مثلا بنویس: /buy 7days"""
    bot.reply_to(message, text)

@bot.message_handler(commands=['buy'])
def buy_plan(message):
    try:
        _, plan_key = message.text.split()
        if plan_key not in PLANS:
            bot.reply_to(message, "❌ پلن نامعتبر")
            return
        address = get_payment_address(message.from_user.id, plan_key)
        bot.reply_to(message, f"برای پرداخت {PLANS[plan_key]['price']} USDT:
💳 آدرس:
`{address}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ فرمت درست نیست. استفاده کن از /buy 7days")

# --- دریافت آدرس اختصاصی از CryptAPI ---
def get_payment_address(user_id, plan_key):
    callback_url = f"https://{REPLIT_PROJECT}/webhook"
    res = requests.get("https://api.cryptapi.io/usdt-trc20/create/", params={
        "callback": callback_url,
        "address": USDT_ADDRESS,
        "custom": f"{user_id}_{plan_key}"
    })
    return res.json().get("address")

# --- وب‌هوک پرداخت ---
app = Flask(__name__)

@app.route('/webhook')
def webhook():
    data = request.args
    user_data = data.get('custom')
    tx_value = float(data.get('value', 0)) / 1e6

    if user_data:
        user_id, plan_key = user_data.split("_")
        plan = PLANS.get(plan_key)
        if plan and tx_value >= plan['price']:
            activate_user(int(user_id), plan['days'])
            bot.send_message(int(user_id), f"✅ اشتراک شما برای {plan['days']} روز فعال شد.")
    return "OK"

# --- اجرای فلَسک ---
def run_flask():
    app.run(host="0.0.0.0", port=8080)
Thread(target=run_flask).start()

# --- تحلیل اخبار اقتصادی (NewsAPI) ---
def fetch_economic_news():
    url = f"https://newsapi.org/v2/top-headlines?q=gold+usd+inflation+economy&language=en&apiKey={NEWSAPI_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        return [a["title"] for a in articles[:3]]
    return []

# --- تحلیل تکنیکال ساده با MACD و RSI از TwelveData ---
def fetch_technical_analysis():
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=50&apikey={TWELVEDATA_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get("values", [])
        closes = [float(x["close"]) for x in reversed(data)]
        macd_signal = calculate_macd_signal(closes)
        rsi_signal = calculate_rsi_signal(closes)
        return macd_signal, rsi_signal
    return None, None

def calculate_macd_signal(closes):
    exp1 = np.array(pd.Series(closes).ewm(span=12, adjust=False).mean())
    exp2 = np.array(pd.Series(closes).ewm(span=26, adjust=False).mean())
    macd = exp1 - exp2
    signal = pd.Series(macd).ewm(span=9, adjust=False).mean()
    if macd[-1] > signal.iloc[-1] and macd[-2] <= signal.iloc[-2]:
        return "MACD_CROSS_UP"
    elif macd[-1] < signal.iloc[-1] and macd[-2] >= signal.iloc[-2]:
        return "MACD_CROSS_DOWN"
    return "MACD_NEUTRAL"

def calculate_rsi_signal(closes, period=14):
    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    if avg_loss == 0:
        return "RSI_OVERBOUGHT"
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    if rsi < 30:
        return "RSI_OVERSOLD"
    elif rsi > 70:
        return "RSI_OVERBOUGHT"
    return "RSI_NEUTRAL"

# --- ربات ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام فرنام! ربات فعال شد. برای اشتراک دستور /subscribe رو بزن.")

@bot.message_handler(commands=['signal'])
def send_signal(message):
    if not is_user_active(message.from_user.id):
        bot.reply_to(message, "❌ اشتراک شما فعال نیست. دستور /subscribe را بزنید.")
        return
    bot.send_message(message.chat.id, "📈 سیگنال تست ارسال شد!")

# --- اجرای تحلیل و ارسال خودکار هر ۵ دقیقه ---
def main_job():
    print("🔍 تحلیل بازار...")
    bot.send_message(ADMIN_ID, "⏰ اجرای تحلیل بازار و ارسال سیگنال")

    macd_signal, rsi_signal = fetch_technical_analysis()
    bot.send_message(ADMIN_ID, f"📉 MACD: {macd_signal}, RSI: {rsi_signal}")

    news_list = fetch_economic_news()
    if news_list:
        bot.send_message(ADMIN_ID, "📰 آخرین اخبار اقتصادی:")
        for news in news_list:
            sentiment = sentiment_analyzer(news)[0]
            label = sentiment['label']
            score = sentiment['score']
            emoji = "🟢" if label == "POSITIVE" else ("🔴" if label == "NEGATIVE" else "⚪")
            bot.send_message(ADMIN_ID, f"{emoji} [{label} | {round(score,2)}] {news}")

schedule.every(5).minutes.do(main_job)

# --- اجرای دائمی ---
print("🤖 ربات پرداخت و سیگنال‌دهی فعال شد...")
while True:
    schedule.run_pending()
    time.sleep(1)
    bot.polling(none_stop=True)
