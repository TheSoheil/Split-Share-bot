from typing import Final
import os
import logging
from dotenv import load_dotenv
from telegram import Update
from collections import defaultdict
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
        "/start — بزن روشن شم\n"
        "/help — بزنی بهت میگم هر دستور چیکارم میکنه\n"
        "/join — بزن تا اد بشی تو خرج\n"
        "/add — بزن تا یه خرجی که خودت کردی رو اضافه کنم\n"
        "/balance — اینو بزنی میگم کی چقدر بدهکاره کی چقدر طلبکار\n"
        "/settle — بزن تا بهت بگم کی باید چقدر بزنه به کی\n"
        "/reset — بزن تا کل داستان رو حذف کنم\n"
        "ایده داری بده تا قوی تر شم"
    )


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
        await update.message.reply_text(
            "❗ Amount must be a positive number like 42 or 42.50"
        )
        return
    amount = float(amount_str)

    # 3. build note
    note = " ".join(context.args[1:]) or "no description"

    # 4. split equally among *current* members
    real_members = list(GROUPS[chat_id]["members"].keys())
    ghosts = list(GROUPS[chat_id].get("ghosts", {}).keys())
    split_between = real_members + ghosts
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


GHOST_SEQ = 0  # global counter for unique ghost ids


async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/invite <name>  – add a guest who isn't in the chat."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in GROUPS or user.id not in GROUPS[chat_id]["members"]:
        await update.message.reply_text("❕ You have to /join first.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /invite <guest name>")
        return

    name = " ".join(context.args)
    global GHOST_SEQ
    GHOST_SEQ += 1
    ghost_id = f"ghost_{GHOST_SEQ}"

    GROUPS[chat_id].setdefault("ghosts", {})[ghost_id] = name
    await update.message.reply_text(f"👤 Guest added: {name}")


def _compute_balances(chat_id: int) -> dict[int, float]:
    """Return dict user_id → net balance (positive = owed, negative = owes)."""
    balances: defaultdict[int, float] = defaultdict(float)
    members = {**GROUPS[chat_id]["members"], **GROUPS[chat_id].get("ghosts", {})}
    for exp in GROUPS[chat_id]["expenses"]:
        n = len(exp["split_between"])
        payer = exp["by"]
        per_person = exp["amount"] / n
        # payer is owed by everyone else
        for uid in exp["split_between"]:
            if uid == payer:
                balances[uid] += (n - 1) * per_person
            else:
                balances[uid] -= per_person
    return balances


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/balance – show current running totals."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUPS or not GROUPS[chat_id]["expenses"]:
        await update.message.reply_text("ℹ️ No expenses yet.")
        return

    members = GROUPS[chat_id]["members"]
    balances = _compute_balances(chat_id)

    lines = []
    for uid, name in members.items():
        b = balances.get(uid, 0.0)
        if b > 0:
            lines.append(f"{name} is owed **{b:.2f}**")
        elif b < 0:
            lines.append(f"{name} owes **{-b:.2f}**")
        else:
            lines.append(f"{name} — settled ✔️")

    await update.message.reply_text("📊 Current balances:\n" + "\n".join(lines))


def _settle_plan(balances: dict[int, float]) -> list[str]:
    """Return list of 'A pays B xx.xx' strings that zero all balances."""
    # split into creditors and debtors
    creditors = [(uid, b) for uid, b in balances.items() if b > 0.01]
    debtors = [(uid, -b) for uid, b in balances.items() if b < -0.01]

    creditors.sort(key=lambda x: x[1])  # smallest first
    debtors.sort(key=lambda x: x[1])  # smallest first

    plan = []
    while creditors and debtors:
        c_uid, c_amt = creditors.pop()  # biggest creditor
        d_uid, d_amt = debtors.pop()  # biggest debtor

        pay = min(c_amt, d_amt)
        plan.append((d_uid, c_uid, pay))

        c_amt -= pay
        d_amt -= pay
        if c_amt > 0.01:
            creditors.append((c_uid, c_amt))
            creditors.sort(key=lambda x: x[1])
        if d_amt > 0.01:
            debtors.append((d_uid, d_amt))
            debtors.sort(key=lambda x: x[1])

    return plan


async def settle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/settle – show minimal payment plan to zero all balances."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUPS or not GROUPS[chat_id]["expenses"]:
        await update.message.reply_text("ℹ️ Nothing to settle.")
        return

    members = GROUPS[chat_id]["members"]
    balances = _compute_balances(chat_id)

    # if everyone is already zero
    if all(abs(b) < 0.01 for b in balances.values()):
        await update.message.reply_text("✅ Everyone is settled!")
        return

    plan = _settle_plan(balances)
    lines = [f"{members[d]} → {members[c]} **{amt:.2f}**" for d, c, amt in plan]
    await update.message.reply_text("💰 Settle up:\n" + "\n".join(lines))


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reset – permanently delete all data for this chat."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUPS:
        await update.message.reply_text("ℹ️ Nothing to reset.")
        return

    # optional safety: require a confirmation word
    if context.args and context.args[0].lower() == "confirm":
        del GROUPS[chat_id]
        await update.message.reply_text("🗑️ All data erased. Start fresh with /join!")
    else:
        await update.message.reply_text(
            "⚠️ This will delete every expense and member.\n" "Type:  `/reset confirm`"
        )


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
