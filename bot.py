
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

# ارسال پیام به کانال
def send_to_channel(text):
    try:
        bot.send_message(CHANNEL_ID, text)
        print("✅ پیام با موفقیت ارسال شد.")
    except Exception as e:
        print(f"❌ ارسال ناموفق: {e}")

# تحلیل نمونه
def main_job():
    send_to_channel("🔔 تست فوری ارسال پیام از سمت ربات!")

# پاسخ به دستور /status
@bot.message_handler(commands=['status'])
def status(message):
    bot.reply_to(message, "✅ ربات آنلاین است و تحلیل انجام می‌دهد.")

# اجرای فقط یک بار برای تست
main_job()
Test message deploy to channel
