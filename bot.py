
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

# لیست ساده کلمات مثبت و منفی
positive_words = ["gain", "rise", "increase", "strong", "bullish", "record", "recovery"]
negative_words = ["fall", "drop", "decrease", "weak", "bearish", "crash", "recession"]

def score_sentiment(text):
    text = text.lower()
    score = sum(1 for word in positive_words if word in text) - sum(1 for word in negative_words if word in text)
    return score

# دریافت اخبار اقتصادی و امتیاز احساسات
def fetch_economic_news_with_sentiment():
    url = "https://api.twelvedata.com/news"
    params = {
        "symbol": "XAU/USD",
        "apikey": "30e73a1373474b43912716946c754e08"
    }
    try:
        res = requests.get(url, params=params).json()
        scored_news = []
        for item in res.get('data', [])[:5]:
            title = item['title']
            score = score_sentiment(title)
            scored_news.append((title, score))
        return scored_news
    except:
        return []

# ارسال به کانال
def send_to_channel(text):
    try:
        bot.send_message(CHANNEL_ID, text)
        print("✅ پیام ارسال شد.")
    except Exception as e:
        print(f"❌ ارسال ناموفق: {e}")

# اجرای تحلیل و ارسال اخبار امتیازدهی شده
def main_job():
    print("📊 تحلیل احساسات اخبار در حال اجرا...")
    news = fetch_economic_news_with_sentiment()
    if news:
        send_to_channel("🧠 تحلیل احساسات روی اخبار اقتصادی:")
        for title, score in news:
            emoji = "🟢" if score > 0 else "🔴" if score < 0 else "⚪"
            send_to_channel(f"{emoji} {title} (امتیاز: {score})")
    else:
        print("❌ خبری دریافت نشد.")

# پاسخ به دستور /sentiment
@bot.message_handler(commands=['sentiment'])
def status(message):
    bot.reply_to(message, "تحلیل احساسات روی اخبار اقتصادی فعال است.")

# اجرای خودکار هر 5 دقیقه
schedule.every(15).minutes.do(main_job)

# شروع برنامه
print("🤖 تحلیلگر احساسات اخبار اقتصادی فعال شد...")
while True:
    schedule.run_pending()
    time.sleep(1)
