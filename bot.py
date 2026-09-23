# bot.py - bot ka main file, yahan se run karte hain
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          ContextTypes, filters)

from config import BOT_TOKEN, REFERRAL_BONUS, DAILY_BONUS, CURRENCY
import database as db

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO)
logger = logging.getLogger(__name__)

# Neeche wale buttons user ko keyboard par dikhenge
BTN_BALANCE = "💰 Balance"
BTN_REFER = "👥 Refer & Earn"
BTN_BONUS = "🎁 Daily Bonus"
MENU = ReplyKeyboardMarkup(
    [[BTN_BALANCE, BTN_BONUS], [BTN_REFER]], resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start - registration + referral link se aaye user ko handle karta hai."""
    user = update.effective_user

    # Link format: t.me/BotName?start=12345 -> context.args = ["12345"]
    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])

    is_new, valid_ref = await db.register_user(
        user.id, user.username, user.first_name, referrer_id)

    if is_new and valid_ref:
        # Referrer ko batao ki naya member judaa
        try:
            await context.bot.send_message(
                valid_ref,
                f"🎉 Aapke link se {user.first_name} judaa! "
                f"+{CURRENCY}{REFERRAL_BONUS} mil gaye.")
        except Exception:
            # Agar referrer ne bot block kar diya ho to ignore karo
            logger.warning("Referrer %s ko message nahi gaya", valid_ref)

    await update.message.reply_text(
        f"Namaste {user.first_name}! 👋\nNeeche ke menu se chuniye.",
        reply_markup=MENU)


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Balance aur referral count dikhata hai."""
    data = await db.get_user(update.effective_user.id)
    if not data:
        await update.message.reply_text("Pehle /start dabayein.")
        return
    await update.message.reply_text(
        f"💰 Balance: {CURRENCY}{data['balance']:.2f}\n"
        f"👥 Total referrals: {data['referral_count']}")


async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ka apna referral link banata hai."""
    uid = update.effective_user.id
    link = f"https://t.me/{context.bot.username}?start={uid}"
    await update.message.reply_text(
        f"👥 Har dost par {CURRENCY}{REFERRAL_BONUS} kamaiye!\n\n"
        f"Aapka link:\n{link}")


async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roz ka bonus (24 ghante mein ek baar)."""
    ok, hours_left = await db.claim_daily_bonus(update.effective_user.id)
    if ok:
        await update.message.reply_text(
            f"🎁 {CURRENCY}{DAILY_BONUS} bonus mil gaya! Kal phir aana.")
    else:
        await update.message.reply_text(
            f"⏳ Agla bonus {hours_left:.1f} ghante baad milega.")


async def post_init(app: Application):
    """Bot chalne se pehle database taiyaar karta hai."""
    await db.init_db()
    logger.info("Database ready")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Text([BTN_BALANCE]), balance))
    app.add_handler(MessageHandler(filters.Text([BTN_REFER]), refer))
    app.add_handler(MessageHandler(filters.Text([BTN_BONUS]), daily_bonus))

    logger.info("Bot start ho gaya")
    app.run_polling()


if __name__ == "__main__":
    main()