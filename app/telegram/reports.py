import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    filters,
)
from api_client import ReportServiceAPI
from app.logger import logger

CONVERSATION_TIMEOUT = 300
TELEGRAM_BOT_TOKEN = "7716843660:AAGjNSCz69hwgIrLHV23kt1Dnatt1CnghKI"
API_BASE_URL = "http://15.207.59.232:8000"


BROKER_CODE, PAN_NUMBER = range(2)

api_client = ReportServiceAPI(API_BASE_URL)

async def start(update: Update, context: CallbackContext) -> int:
    """Start the conversation and ask for the broker code."""
    await update.message.reply_text(
        "Welcome to Plus91 Reports Bot! 📊\n\n"
        "I can help you receive your investment reports via email.\n\n"
        "Please enter your Broker Code:"
    )
    return BROKER_CODE

async def broker_code(update: Update, context: CallbackContext) -> int:
    """Store the broker code and ask for the PAN number."""
    user_broker_code = update.message.text.strip()
    
    if not user_broker_code:
        await update.message.reply_text(
            "Broker Code cannot be empty. Please enter your Broker Code:"
        )
        return BROKER_CODE
    
    context.user_data["broker_code"] = user_broker_code
    
    await update.message.reply_text(
        f"Thanks! Now please enter your PAN Number:"
    )
    return PAN_NUMBER

async def pan_number(update: Update, context: CallbackContext) -> int:
    """Store the PAN number and process the request."""
    user_pan_number = update.message.text.strip().upper()
    
    if not user_pan_number or len(user_pan_number) != 10:
        await update.message.reply_text(
            "Invalid PAN Number format. PAN should be 10 characters long.\n"
            "Please enter your PAN Number again:"
        )
        return PAN_NUMBER
    
    context.user_data["pan_no"] = user_pan_number
    
    processing_message = await update.message.reply_text(
        "Processing your request... Please wait."
    )
    success, result = await api_client.send_report_request(
        context.user_data["broker_code"],
        context.user_data["pan_no"]
    )
    
    if success:
        await processing_message.edit_text(
            "✅ Success! Your reports have been sent to your registered email address.\n\n"
            "If you need more reports, just send /start to begin again."
        )
    else:
        error_message = result.get("error", "Unknown error occurred")
        await processing_message.edit_text(
            f"❌ Sorry, we couldn't process your request: {error_message}\n\n"
            "Please try again by sending /start or contact support if the issue persists."
        )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operation cancelled. Your information has been discarded.\n"
        "Send /start to begin again when you're ready."
    )
    context.user_data.clear()
    
    return ConversationHandler.END

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "This bot helps you receive your Plus91 investment reports via email.\n\n"
        "Available commands:\n"
        "/start - Start the process to request your reports\n"
        "/cancel - Cancel the current operation\n"
        "/help - Show this help message"
    )

async def timeout(update: Update, context: CallbackContext) -> int:
    """Handle conversation timeout."""
    await update.message.reply_text(
        "Our conversation has timed out for security reasons.\n"
        "Please send /start to begin again when you're ready."
    )
    context.user_data.clear()
    
    return ConversationHandler.END

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors in the bot."""
    logger.error(f"Error occurred: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Sorry, an error occurred while processing your request.\n"
            "Please try again later or contact support."
        )

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            BROKER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broker_code)],
            PAN_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, pan_number)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
