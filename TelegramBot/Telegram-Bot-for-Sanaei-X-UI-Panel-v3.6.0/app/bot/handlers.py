"""
Telegram bot command handlers.
All business logic for bot commands is implemented here.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import logging

from app.bot.messages import START_MESSAGE, HELP_MESSAGE, ERROR_MESSAGE

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    Shows welcome message.
    """
    user = update.effective_user
    logger.info(f"User {user.id} (@{user.username}) started the bot")
    
    try:
        await update.message.reply_text(START_MESSAGE)
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text(ERROR_MESSAGE.format(error=str(e)))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command.
    Shows available commands.
    """
    user = update.effective_user
    logger.info(f"User {user.id} requested help")
    
    try:
        await update.message.reply_text(HELP_MESSAGE)
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text(ERROR_MESSAGE.format(error=str(e)))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /status command.
    Placeholder for future implementation.
    """
    user = update.effective_user
    logger.info(f"User {user.id} requested status")
    
    await update.message.reply_text(
        "⏳ در حال توسعه...\n"
        "به زودی وضعیت سرور نمایش داده می‌شود."
    )


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /add_user command.
    Placeholder for future implementation.
    """
    user = update.effective_user
    logger.info(f"User {user.id} requested add_user")
    
    await update.message.reply_text(
        "⏳ در حال توسعه...\n"
        "به زودی می‌توانید کاربر جدید ایجاد کنید."
    )


def get_handlers():
    """
    Returns list of bot handlers.
    This function is used by main.py to register all handlers.
    """
    return [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("status", status_command),
        CommandHandler("add_user", add_user_command),
    ]