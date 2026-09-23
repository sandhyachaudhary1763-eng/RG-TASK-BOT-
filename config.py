# config.py - saari settings ek jagah, taaki baad mein aasaani se badal sakein
import os
from dotenv import load_dotenv

load_dotenv()  # .env file se values padhta hai

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Admin IDs comma se alag karke likhte hain, jaise 111,222
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

DB_PATH = "earning_bot.db"

# Paisa/points ki settings (apne hisaab se badlein)
SIGNUP_BONUS = 1.0        # naye user ko milne wala bonus
REFERRAL_BONUS = 5.0      # har valid referral par referrer ko bonus
DAILY_BONUS = 0.5         # roz ka bonus
DAILY_COOLDOWN_HOURS = 24
CURRENCY = "₹"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env file mein set nahi hai")
# ---- Phase 2 settings ----
MIN_WITHDRAWAL = 50.0          # minimum withdrawal amount
TASK_MIN_WAIT_SECONDS = 15     # link-task claim karne se pehle kam se kam itna wait

# Force-join channels (.env se). Khali chhodne par force-join band rahega.
REQUIRED_CHANNELS = [
    c.strip() for c in os.getenv("REQUIRED_CHANNELS", "").split(",") if c.strip()
]