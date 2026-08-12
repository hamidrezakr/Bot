# app/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from app.config import BOT_TOKEN, WEBHOOK_PORT
from app.bot.handlers import (
    start, services, check_user, buy, help_command, menu_command,
    my_status_start, handle_message, cancel, receive_receipt,
    buy_manual, manual_pay_selected, receive_renew_email, renew_start, renew_confirm, renew_create_payment
)
from app.bot.callbacks import handle_callback
from app.api.webhook import router as webhook_router
from app.api.health import router as health_router
from app.api.admin import router as admin_router
from app.api.admin_auth import router as admin_auth_router
from app.models.database import init_db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logging.info("✅ Database initialized")
    
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("services", services))
    bot_app.add_handler(CommandHandler("check", check_user))
    bot_app.add_handler(CommandHandler("buy", buy))
    bot_app.add_handler(CommandHandler("help", help_command))
    bot_app.add_handler(CommandHandler("menu", menu_command))
    bot_app.add_handler(CommandHandler("mystatus", my_status_start))
    bot_app.add_handler(CommandHandler("cancel", cancel))
    bot_app.add_handler(CommandHandler("renew", renew_start))
    
    # Message handlers
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(MessageHandler(filters.PHOTO, receive_receipt))
    
    # Callback handler
    bot_app.add_handler(CallbackQueryHandler(handle_callback))
    
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    
    logging.info("✅ Telegram bot started successfully")
    
    yield
    
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(title="VPN Telegram Bot", lifespan=lifespan)

app.include_router(webhook_router)
app.include_router(health_router)
app.include_router(admin_router)
app.include_router(admin_auth_router)

@app.get("/")
async def root():
    return {"status": "ok", "message": "VPN Bot is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)