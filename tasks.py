# tasks.py - tasks dikhana, claim karna, aur admin ke task commands
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError

from config import ADMIN_IDS, CURRENCY, TASK_MIN_WAIT_SECONDS
import db_phase2 as p2
from force_join import require_join

logger = logging.getLogger(__name__)


@require_join
async def show_tasks(update, context):
    """Us user ke liye bache hue saare tasks button ki tarah dikhata hai."""
    tasks = await p2.get_pending_tasks_for_user(update.effective_user.id)
    if not tasks:
        await update.message.reply_text("✅ Abhi koi naya task nahi hai. Baad mein check karein.")
        return
    buttons = [
        [InlineKeyboardButton(
            f"{t['title']} (+{CURRENCY}{t['reward']:g})",
            callback_data=f"task_{t['id']}")]
        for t in tasks
    ]
    await update.message.reply_text("📝 Available tasks:", reply_markup=InlineKeyboardMarkup(buttons))


async def task_open(update, context):
    """Task ki details + 'Link kholein' aur 'Claim' buttons."""
    query = update.callback_query
    task_id = int(query.data.split("_")[1])
    task = await p2.get_task(task_id)
    if not task or not task["is_active"]:
        await query.answer("Ye task ab available nahi hai.", show_alert=True)
        return

    # Kab khola gaya, ye yaad rakhte hain (link-tasks mein wait time check ke liye)
    context.user_data[f"task_opened_{task_id}"] = time.time()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Task Kholein", url=task["url"])],
        [InlineKeyboardButton("✅ Claim Reward", callback_data=f"claim_{task_id}")],
    ])
    await query.answer()
    await query.edit_message_text(
        f"📝 {task['title']}\n"
        f"Reward: {CURRENCY}{task['reward']:g}\n\n"
        "1) Link kholkar task poora karein\n"
        "2) Phir 'Claim Reward' dabayein",
        reply_markup=keyboard)


async def task_claim(update, context):
    """Verification ke baad reward deta hai."""
    query = update.callback_query
    user_id = query.from_user.id
    task_id = int(query.data.split("_")[1])

    task = await p2.get_task(task_id)
    if not task or not task["is_active"]:
        await query.answer("Ye task ab available nahi hai.", show_alert=True)
        return

    if task["chat_id"]:
        # Channel-join task: sach mein join kiya ya nahi, Telegram se pooch kar verify
        try:
            member = await context.bot.get_chat_member(task["chat_id"], user_id)
        except TelegramError as e:
            logger.error("Task %s verify nahi hua: %s", task_id, e)
            await query.answer("Verify nahi ho paaya, thodi der baad try karein.", show_alert=True)
            return
        if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            await query.answer("❌ Pehle channel join karein.", show_alert=True)
            return
    else:
        # Link-task: verify nahi ho sakta, isliye kam se kam wait time lagate hain
        opened_at = context.user_data.get(f"task_opened_{task_id}")
        if not opened_at or time.time() - opened_at < TASK_MIN_WAIT_SECONDS:
            await query.answer(
                f"⏳ Pehle task poora karein, {TASK_MIN_WAIT_SECONDS} sec baad claim karein.",
                show_alert=True)
            return

    reward = await p2.complete_task(user_id, task_id)
    if reward is None:
        await query.answer("Ye task pehle hi complete ho chuka hai.", show_alert=True)
        return

    await query.answer("🎉 Reward mil gaya!")
    await query.edit_message_text(
        f"✅ Task complete! +{CURRENCY}{reward:g} aapke balance mein add ho gaya.")


# ---------------------- ADMIN COMMANDS ----------------------

async def add_task_cmd(update, context):
    """/addtask Title | https://link | reward | @channel (channel optional)"""
    if update.effective_user.id not in ADMIN_IDS:
        return  # non-admin ko koi jawab nahi

    parts = [p.strip() for p in " ".join(context.args).split("|")]
    if len(parts) < 3:
        await update.message.reply_text(
            "Format:\n/addtask Title | https://link | reward | @channel\n"
            "(@channel sirf channel-join task ke liye, baaki mein chhod dein)")
        return

    title, url, reward_text = parts[0], parts[1], parts[2]
    chat_id = parts[3] if len(parts) > 3 and parts[3] else None

    try:
        reward = float(reward_text)
        if reward <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Reward sahi number hona chahiye.")
        return
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ URL http:// ya https:// se shuru hona chahiye.")
        return
    if chat_id and not chat_id.startswith("@"):
        await update.message.reply_text("❌ Channel @username format mein likhein.")
        return

    task_id = await p2.add_task(title, url, reward, chat_id)
    await update.message.reply_text(f"✅ Task #{task_id} add ho gaya.")


async def del_task_cmd(update, context):
    """/deltask <id> - task band karta hai."""
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Format: /deltask <task_id>")
        return
    ok = await p2.deactivate_task(int(context.args[0]))
    await update.message.reply_text("✅ Task band kar diya." if ok else "❌ Task nahi mila.")