# keyboards.py - menu ke buttons ek jagah, taaki har file yahin se import kare
from telegram import ReplyKeyboardMarkup

BTN_BALANCE = "💰 Balance"
BTN_BONUS = "🎁 Daily Bonus"
BTN_TASKS = "📝 Tasks"
BTN_REFER = "👥 Refer & Earn"
BTN_WITHDRAW = "💸 Withdraw"

MENU = ReplyKeyboardMarkup(
    [[BTN_BALANCE, BTN_BONUS],
     [BTN_TASKS, BTN_REFER],
     [BTN_WITHDRAW]],
    resize_keyboard=True,
)