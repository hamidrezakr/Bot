from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx
import os

# ============ تنظیمات اولیه ============
# توکن بات را از تلگرام دریافت کنید
BOT_TOKEN = "YOUR_BOT_TOKEN"  # بعداً این را عوض کن

# اطلاعات پنل X-UI (بعداً تنظیم می‌شود)
XUI_URL = "http://your-server-ip:port"
XUI_USERNAME = "admin"
XUI_PASSWORD = "admin"

# ============ راه‌اندازی بات تلگرام ============
# اینجا بات را به صورت Polling (غیر Webhook) راه‌اندازی می‌کنیم
# چون تازه شروع کردیم و ساده‌تر است

app_bot = Application.builder().token(BOT_TOKEN).build()

# ============ تعریف دستورات بات ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start"""
    await update.message.reply_text(
        "سلام! به بات مدیریت پنل X-UI خوش آمدید.\n"
        "برای مشاهده‌ی راهنما، /help را بزنید."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /help"""
    await update.message.reply_text(
        "دستورات موجود:\n"
        "/start - شروع بات\n"
        "/help - راهنما\n"
        "/status - وضعیت سرور\n"
        "/add_user - ایجاد کاربر جدید (به زودی)\n"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /status - وضعیت سرور را نشان می‌دهد"""
    try:
        # اینجا باید به پنل X-UI متصل شوید
        # فعلاً یک پیام آزمایشی می‌فرستیم
        await update.message.reply_text("🟢 سرور آنلاین است!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")

# ============ ثبت دستورات در بات ============
app_bot.add_handler(CommandHandler("start", start))
app_bot.add_handler(CommandHandler("help", help_command))
app_bot.add_handler(CommandHandler("status", status))

# ============ FastAPI ============
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "بات تلگرام X-UI Panel در حال اجراست!"}

@app.post("/webhook")
async def webhook(request: Request):
    """Webhook برای دریافت پیام‌های تلگرام (در آینده)"""
    return {"status": "ok"}

# ============ اجرای برنامه ============
if __name__ == "__main__":
    import uvicorn
    # اجرای بات به صورت Polling
    print("🤖 بات تلگرام در حال اجرا...")
    app_bot.run_polling()