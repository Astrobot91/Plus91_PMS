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

CONVERSATION_TIMEOUT = 300  # 5 minutes
TELEGRAM_BOT_TOKEN = "7716843660:AAGjNSCz69hwgIrLHV23kt1Dnatt1CnghKI"
API_BASE_URL = "http://15.207.59.232:8000"

BROKER_CODE, PAN_NUMBER = range(2)

api_client = ReportServiceAPI(API_BASE_URL)

async def start(update: Update, context: CallbackContext) -> int:
    """Start the conversation and ask for the broker code."""
    context.user_data.clear()  # Clear any existing data
    await update.message.reply_text(
        "Welcome to Plus91 Reports Service 📊\n\n"
        "To receive your investment reports, please provide:\n"
        "1. Your Broker Code (Example: ABC123)\n"
        "2. Your PAN Number\n\n"
        "Please enter your Broker Code:"
    )
    return BROKER_CODE

async def broker_code(update: Update, context: CallbackContext) -> int:
    """Store the broker code and ask for the PAN number."""
    user_broker_code = update.message.text.strip()
    
    if not user_broker_code:
        await update.message.reply_text(
            "The Broker Code field cannot be empty.\n"
            "Please provide your Broker Code as assigned by your broker.\n\n"
            "Use /start to begin again or /cancel to exit."
        )
        return BROKER_CODE
    
    context.user_data["broker_code"] = user_broker_code
    
    await update.message.reply_text(
        "Please enter your PAN Number.\n"
        "Note: The PAN should be 10 characters in length.\n\n"
        "Use /start to begin again if you need to correct your Broker Code."
    )
    return PAN_NUMBER

async def pan_number(update: Update, context: CallbackContext) -> int:
    """Store the PAN number and process the request."""
    user_pan_number = update.message.text.strip().upper()
    
    if not user_pan_number or len(user_pan_number) != 10:
        await update.message.reply_text(
            "Invalid PAN Number format.\n"
            "Please enter a valid 10-character PAN Number.\n"
            "Format: AAAAA0000A\n\n"
            "Use /start to begin again if needed."
        )
        return PAN_NUMBER
    
    context.user_data["pan_no"] = user_pan_number
    
    processing_message = await update.message.reply_text(
        "Processing your request. Please wait while we generate your reports."
    )
    success, result = await api_client.send_report_request(
        context.user_data["broker_code"],
        context.user_data["pan_no"]
    )
    
    if success:
        await processing_message.edit_text(
            "Your investment reports have been successfully generated and sent to your registered email address. ✉️\n\n"
            "To request additional reports, use the /start command."
        )
    else:
        error_message = result.get("error", "An unexpected error occurred")
        await processing_message.edit_text(
            f"Request processing failed: {error_message}\n\n"
            "Please try again using /start or contact our support team for assistance."
        )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Request cancelled. All entered information has been cleared.\n"
        "To start a new request, use the /start command."
    )
    context.user_data.clear()
    return ConversationHandler.END

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Plus91 Reports Service - Help\n\n"
        "This service provides access to your investment reports via email.\n\n"
        "Available Commands:\n"
        "/start - Initialize a new report request (can be used anytime to start over)\n"
        "/cancel - Exit the current operation\n"
        "/help - Display this information\n\n"
        "For additional assistance, please contact our support team."
    )

async def timeout(update: Update, context: CallbackContext) -> int:
    """Handle conversation timeout."""
    await update.message.reply_text(
        "The session has expired for security purposes.\n"
        "Please use /start to begin a new request."
    )
    context.user_data.clear()
    return ConversationHandler.END

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors in the bot."""
    logger.error(f"Error occurred: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "An error occurred while processing your request.\n"
            "Please try again later or contact our support team for assistance."
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
        fallbacks=[
            CommandHandler("start", start),  # Allow restart at any point
            CommandHandler("cancel", cancel)
        ],
        conversation_timeout=CONVERSATION_TIMEOUT
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
