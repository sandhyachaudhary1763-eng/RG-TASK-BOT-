# force_join.py - user ko pehle channels join karwane ka system
import logging
from functools import wraps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import ConversationHandler

from config import REQUIRED_CHANNELS
from keyboards import MENU

logger = logging.getLogger(__name__)


async def get_missing_channels(bot, user_id: int) -> list:
    """Wo channels jo user ne join nahi kiye. Sab join hain to khali list."""
    missing = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
                missing.append(channel)
        except TelegramError as e:
            # Aksar tab hota hai jab bot us channel mein admin nahi hai.
            # Users ko na rokein, bas log mein error dikhayein.
            logger.error("Channel %s check nahi hua: %s", channel, e)
    return missing


async def send_join_prompt(bot, chat_id: int, channels: list) -> None:
    """Join karne ke buttons + 'Maine join kar liya' button bhejta hai."""
    rows = [
        [InlineKeyboardButton(f"📢 Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")]
        for ch in channels
    ]
    rows.append([InlineKeyboardButton("✅ Maine Join Kar Liya", callback_data="check_join")])
    await bot.send_message(
        chat_id,
        "⚠️ Bot use karne ke liye pehle ye channels join karein:",
        reply_markup=InlineKeyboardMarkup(rows))


def require_join(handler):
    """Decorator: handler chalne se pehle channel membership check karta hai."""
    @wraps(handler)
    async def wrapper(update, context, *args, **kwargs):
        if REQUIRED_CHANNELS:
            missing = await get_missing_channels(context.bot, update.effective_user.id)
            if missing:
                await send_join_prompt(context.bot, update.effective_chat.id, missing)
                return ConversationHandler.END  # conversation ho to wahin rok do
        return await handler(update, context, *args, **kwargs)
    return wrapper


async def check_join_callback(update, context):
    """'Maine Join Kar Liya' button dabane par dobara check karta hai."""
    query = update.callback_query
    missing = await get_missing_channels(context.bot, query.from_user.id)
    if missing:
        await query.answer("❌ Aapne abhi sabhi channels join nahi kiye.", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text("✅ Verify ho gaya!")
    await context.bot.send_message(
        query.from_user.id, "Ab menu use kar sakte hain 👇", reply_markup=MENU)