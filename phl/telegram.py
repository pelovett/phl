import logging
import os
import sys
import traceback

from langchain_core.runnables import Runnable
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages.ai import AIMessage
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from phl.agent import process_message


def get_handler(model, telegram_user_id: int):
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context._user_id != telegram_user_id:
            logging.warning("Ignoring message from different user id...")
            return

        if update.message is None:
            logging.warning("Unknown telegram update type: %s", update)
            return

        if update.message.text is None:
            logging.warning("User message has no text: %s", update.message)
            return

        send_chat_promise = context.bot.send_chat_action(
            update.message.chat_id, action="typing"
        )
        process_msg_promise = process_message(model, update.message)
        await send_chat_promise
        await process_msg_promise

    return handle_message


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    tb = "".join(
        traceback.format_exception(
            type(context.error) if context.error else None,
            context.error,
            context.error.__traceback__ if context.error else None,
        )
    )
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            f"❌ Error:\n\n<pre>{tb}</pre>", parse_mode="HTML"
        )


def get_app(model: Runnable[LanguageModelInput, AIMessage]):
    telegram_api_key = os.getenv("TELEGRAM_API_KEY")
    if telegram_api_key is None:
        logging.error("Must set TELEGRAM_API_KEY")
        sys.exit(1)

    telegram_user_id = os.getenv("TELEGRAM_USER_ID")
    if telegram_user_id is None:
        logging.error("Must set TELEGRAM_USER_ID")
        sys.exit(1)
    try:
        telegram_user_id = int(telegram_user_id)
    except Exception:
        raise ValueError("TELEGRAM_USER_ID must be int, not: " + telegram_user_id)

    app = ApplicationBuilder().token(telegram_api_key).build()
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, get_handler(model, telegram_user_id)
        )
    )
    app.add_error_handler(error_handler)
    return app
