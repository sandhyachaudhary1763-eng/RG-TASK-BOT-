# withdraw.py - withdrawal ka poora flow + admin approve/reject
import logging
import math
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import (CallbackQueryHandler, CommandHandler,
                          ConversationHandler, MessageHandler, filters)

from config import ADMIN_IDS, CURRENCY, MIN_WITHDRAWAL
import database as db
import db_phase2 as p2
from force_join import require_join
from keyboards import BTN_WITHDRAW, MENU

logger = logging.getLogger(__name__)

# Conversation ke 3 steps
ASK_AMOUNT, ASK_UPI, CONFIRM = range(3)

# UPI ID ka basic format: name@bank
UPI_REGEX = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")


@require_join
async def withdraw_start(update, context):
    """Step 0: eligibility check, phir amount poochna."""
    user = await db.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Pehle /start dabayein.")
        return ConversationHandler.END
    if user["is_banned"]:
        await update.message.reply_text("❌ Aapka account restricted hai.")
        return ConversationHandler.END
    if user["balance"] < MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ Minimum withdrawal {CURRENCY}{MIN_WITHDRAWAL:g} hai.\n"
            f"Aapka balance: {CURRENCY}{user['balance']:.2f}")
        return ConversationHandler.END
    if await p2.has_pending_withdrawal(user["user_id"]):
        await update.message.reply_text("⏳ Aapki ek request pehle se pending hai.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"💸 Kitna nikalna hai?\n"
        f"Min {CURRENCY}{MIN_WITHDRAWAL:g} se max {CURRENCY}{user['balance']:.2f}\n\n"
        "Cancel karne ke liye /cancel")
    return ASK_AMOUNT


async def got_amount(update, context):
    """Step 1: amount check karna."""
    try:
        amount = round(float(update.message.text.strip()), 2)
        if not math.isfinite(amount):  # nan / inf rokne ke liye
            raise ValueError
    except ValueError:
        await update.message.reply_text("Sahi number likhein (jaise 100) ya /cancel")
        return ASK_AMOUNT

    user = await db.get_user(update.effective_user.id)
    if amount < MIN_WITHDRAWAL or amount > user["balance"]:
        await update.message.reply_text(
            f"Amount {CURRENCY}{MIN_WITHDRAWAL:g} aur {CURRENCY}{user['balance']:.2f} "
            "ke beech hona chahiye.")
        return ASK_AMOUNT

    context.user_data["wd_amount"] = amount
    await update.message.reply_text("Ab apni UPI ID likhein (jaise name@upi)")
    return ASK_UPI


async def got_upi(update, context):
    """Step 2: UPI ID check karke confirm mangna."""
    upi = update.message.text.strip()
    if not UPI_REGEX.match(upi):
        await update.message.reply_text("❌ UPI ID galat lag rahi hai. Dobara likhein ya /cancel")
        return ASK_UPI

    context.user_data["wd_upi"] = upi
    amount = context.user_data["wd_amount"]
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data="wd_confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="wd_cancel"),
    ]])
    await update.message.reply_text(
        f"Confirm karein:\nAmount: {CURRENCY}{amount:.2f}\nUPI: {upi}",
        reply_markup=keyboard)
    return CONFIRM


async def confirm(update, context):
    """Step 3: request save karna aur admins ko bhejna."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    amount = context.user_data.pop("wd_amount", None)
    upi = context.user_data.pop("wd_upi", None)
    if amount is None or upi is None:
        await query.edit_message_text("⚠️ Session expire ho gaya. Dobara Withdraw dabayein.")
        return ConversationHandler.END

    withdrawal_id, error = await p2.create_withdrawal(user.id, amount, upi)
    if error == "pending":
        await query.edit_message_text("⏳ Aapki ek request pehle se pending hai.")
        return ConversationHandler.END
    if error:
        await query.edit_message_text("❌ Balance kam hai ya account restricted hai.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"✅ Request #{withdrawal_id} bhej di gayi.\n"
        "Admin approve karega to payment aapki UPI par bheji jayegi.")

    # Har admin ko Approve / Reject buttons ke saath bhejo
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"wd_ok_{withdrawal_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"wd_no_{withdrawal_id}"),
    ]])
    text = (f"💸 New withdrawal #{withdrawal_id}\n"
            f"User: {user.first_name} (ID {user.id})\n"
            f"Amount: {CURRENCY}{amount:.2f}\n"
            f"UPI: {upi}\n\n"
            "Pehle UPI se payment karein, phir Approve dabayein.")
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, reply_markup=keyboard)
        except TelegramError as e:
            logger.warning("Admin %s ko message nahi gaya: %s", admin_id, e)
    return ConversationHandler.END


async def cancel(update, context):
    """/cancel ya Cancel button - flow band karta hai."""
    context.user_data.pop("wd_amount", None)
    context.user_data.pop("wd_upi", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Withdrawal cancel ho gaya.")
    else:
        await update.message.reply_text("❌ Withdrawal cancel ho gaya.", reply_markup=MENU)
    return ConversationHandler.END


async def admin_decision(update, context):
    """Admin ke Approve / Reject button ka handler."""
    query = update.callback_query
    admin_id = query.from_user.id
    if admin_id not in ADMIN_IDS:
        await query.answer("Aap admin nahi hain.", show_alert=True)
        return

    _, action, withdrawal_id = query.data.split("_")  # jaise wd_ok_12
    approve = action == "ok"
    w = await p2.process_withdrawal(int(withdrawal_id), admin_id, approve)
    if w is None:
        await query.answer("Ye request pehle hi process ho chuki hai.", show_alert=True)
        return

    await query.answer("Done")
    status_line = "✅ APPROVED" if approve else "❌ REJECTED (balance wapas ho gaya)"
    await query.edit_message_text(f"{query.message.text}\n\n{status_line} by {admin_id}")

    # User ko natija batao
    if approve:
        msg = f"✅ Aapki withdrawal #{w['id']} ({CURRENCY}{w['amount']:.2f}) approve ho gayi."
    else:
        msg = (f"❌ Aapki withdrawal #{w['id']} reject ho gayi. "
               f"{CURRENCY}{w['amount']:.2f} balance mein wapas aa gaye.")
    try:
        await context.bot.send_message(w["user_id"], msg)
    except TelegramError:
        logger.warning("User %s ko message nahi gaya", w["user_id"])


def build_withdraw_handler() -> ConversationHandler:
    """bot.py mein register karne ke liye poora conversation handler."""
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([BTN_WITHDRAW]), withdraw_start)],
        states={
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_amount)],
            ASK_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_upi)],
            CONFIRM: [
                CallbackQueryHandler(confirm, pattern="^wd_confirm$"),
                CallbackQueryHandler(cancel, pattern="^wd_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )