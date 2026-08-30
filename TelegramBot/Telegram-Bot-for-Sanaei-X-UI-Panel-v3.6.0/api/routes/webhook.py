"""
Webhook route handler for Telegram updates.
"""

from fastapi import APIRouter, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler as PTBMessageHandler, filters

from core.config import settings
from core.logging import logger
from api.handlers.message_handler import MessageHandler


router = APIRouter()
message_handler = MessageHandler()


def create_application() -> Application:
    """
    Create and configure the Telegram application.
    """
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", message_handler.handle_start))
    application.add_handler(
        CallbackQueryHandler(message_handler.handle_callback_query)
    )

    # ====== هندلر برای همه پیام‌ها ======
    application.add_handler(
        PTBMessageHandler(
            filters.ALL & ~filters.COMMAND,
            message_handler.handle_all_messages
        )
    )

    return application


application = create_application()


@router.on_event("startup")
async def startup_application():
    logger.info("Initializing Telegram application...")
    await application.initialize()
    logger.info("Telegram application initialized successfully")


@router.on_event("shutdown")
async def shutdown_application():
    logger.info("Shutting down Telegram application...")
    await application.shutdown()
    logger.info("Telegram application shut down successfully")


@router.post("/webhook")
async def webhook(request: Request) -> Response:
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        logger.info(f"Received webhook update: {update.update_id}")
        await application.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return Response(status_code=500)


@router.post("/set_webhook")
async def set_webhook() -> dict:
    try:
        webhook_url = settings.TELEGRAM_WEBHOOK_URL
        await application.initialize()
        
        # ====== ✅ Set bot commands for menu ======
        commands = [
            ("start", "🚀 شروع"),
        ]
        
        await application.bot.set_my_commands(commands)
        
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set successfully to: {webhook_url}")
        return {"status": "success", "message": f"Webhook set to {webhook_url}"}
    except Exception as e:
        logger.error(f"Error setting webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/delete_webhook")
async def delete_webhook() -> dict:
    try:
        await application.initialize()
        await application.bot.delete_webhook()
        logger.info("Webhook deleted successfully")
        return {"status": "success", "message": "Webhook deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting webhook: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }
