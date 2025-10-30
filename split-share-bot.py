from typing import Final
import os
import logging
from dotenv import load_dotenv
from telegram import Update
import re
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- CONFIG ----------
load_dotenv()
TOKEN: Final[str | None] = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN not found in .env")

BOT_USERNAME: Final = "@DangODong_bot"

# Enable logging so you see every update in the console
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ---------- IN-MEMORY STORAGE (replace with DB later) ----------
# chat_id -> { "members": set[user_id], "expenses": list[dict] }
GROUPS: dict[int, dict] = {}

# ---------- HANDLERS ----------
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Dong Bedid!\n"
        "Commands:\n"
        "/join — include yourself in the group\n"
        "/add <amount> <note> — record an expense you paid (split equally)\n"
        "/balance — show who owes/gets\n"
        "/settle — minimal pay plan\n"
        "/reset — clear data for this chat\n"
        "\nTip: Use decimals like 123.45 (or 123,45)."
    )


async def help_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "/start — greet\n"
        "/help — this help\n"
        "/join — بزن تا اد بشی تو خرج\n"
        "More commands coming soon…"
    )


# ---------- TODO: implement the 5 split commands ----------
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/join – add the sender to the current chat’s member list."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    # 1. create group bucket if it doesn’t exist
    if chat_id not in GROUPS:
        GROUPS[chat_id] = {"members": {}, "expenses": []}

    # 2. add / update member
    GROUPS[chat_id]["members"][user.id] = user.full_name

    # 3. reply
    names = list(GROUPS[chat_id]["members"].values())
    await update.message.reply_text(
        f"✅ {user.full_name} joined!\n"
        f"Current squad ({len(names)}): {', '.join(names)}"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/add <amount> <note> – record an expense split equally among current members."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    # 1. basic validation
    if chat_id not in GROUPS or user.id not in GROUPS[chat_id]["members"]:
        await update.message.reply_text("❕ You have to /join first.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /add <amount> <note>")
        return

    # 2. parse amount (accept comma or dot)
    amount_str = context.args[0].replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", amount_str):
        await update.message.reply_text("❗ Amount must be a positive number like 42 or 42.50")
        return
    amount = float(amount_str)

    # 3. build note
    note = " ".join(context.args[1:]) or "no description"

    # 4. split equally among *current* members
    members = GROUPS[chat_id]["members"]
    split_between = list(members.keys())
    per_person = round(amount / len(split_between), 2)

    # 5. store expense
    GROUPS[chat_id]["expenses"].append(
        {
            "by": user.id,
            "amount": amount,
            "note": note,
            "split_between": split_between,
        }
    )

    # 6. reply
    names = [members[uid] for uid in split_between]
    await update.message.reply_text(
        f"💸 {members[user.id]} paid **{amount:.2f}** for _{note}_\n"
        f"Split between {len(names)} people → **{per_person:.2f}** each:\n"
        + ", ".join(names)
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/balance – show running balances."""
    # TODO
    await update.message.reply_text("🔧 /balance not implemented yet")


async def settle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/settle – compute minimal number of payments to settle."""
    # TODO
    await update.message.reply_text("🔧 /settle not implemented yet")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reset – wipe all data for this chat."""
    # TODO
    await update.message.reply_text("🔧 /reset not implemented yet")


# ---------- FALLBACK ----------
async def echo(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    await update.message.reply_text(f"you said: {text}")


# ---------- MAIN ----------
def main() -> None:
    app = Application.builder().token(TOKEN).build()

    # command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("settle", settle))
    app.add_handler(CommandHandler("reset", reset))

    # non-command text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    log.info("Bot started – polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()