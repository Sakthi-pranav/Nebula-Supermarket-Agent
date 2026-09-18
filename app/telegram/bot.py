import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.config import settings
from app.telegram.handlers import start_command, help_command, reset_command, handle_message

logger = logging.getLogger(__name__)

def create_telegram_app():
    """Create and configure python-telegram-bot Application instance."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == "your_telegram_bot_token_here":
        logger.warning("TELEGRAM_BOT_TOKEN is not set in environment or .env file.")
        token = "DUMMY_TOKEN"

    app = ApplicationBuilder().token(token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))

    # Register message handler for text messages
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    return app

def run_bot():
    """Start Telegram bot in polling mode."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == "your_telegram_bot_token_here":
        print("❌ Cannot start Telegram bot: TELEGRAM_BOT_TOKEN is missing from .env!")
        print("Please configure TELEGRAM_BOT_TOKEN in your .env file and restart.")
        return

    print("🚀 Starting Supermarket Ops Telegram Bot...")
    app = create_telegram_app()
    app.run_polling()

if __name__ == "__main__":
    run_bot()
