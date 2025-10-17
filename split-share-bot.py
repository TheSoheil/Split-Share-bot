from typing import Final
from dotenv import load_dotenv
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)




load_dotenv()  # Load environment variables from .env file

TOKEN = os.getenv("BOT_TOKEN")

bot_username: Final = "@DangODong_bot"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text( # type: ignore
        "👋 SplitBot here!\n"
        "Commands:\n"
        "/join — include yourself in the group\n"
        "/add <amount> <note> — record an expense you paid (split equally)\n"
        "/balance — show who owes/gets\n"
        "/settle — minimal pay plan\n"
        "/reset — clear data for this chat\n"
        "\nTip: Use decimals like 123.45 (or 123,45)."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text( # pyright: ignore[reportOptionalMemberAccess]
        "Commands:\n/start — greet\n/help — this help\n\nSend any text and I’ll echo it perfectly."
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text # pyright: ignore[reportOptionalMemberAccess]
    await update.message.reply_text(f"you said: {text}") # pyright: ignore[reportOptionalMemberAccess]


async def shit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I pooped.")  # type: ignore


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("shit", shit_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()  # long polling for dev


if __name__ == "__main__":
    main()
