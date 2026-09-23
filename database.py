# database.py - saara database ka kaam yahan hota hai
import aiosqlite
from datetime import datetime, timedelta, timezone

from config import (DB_PATH, SIGNUP_BONUS, REFERRAL_BONUS,
                    DAILY_BONUS, DAILY_COOLDOWN_HOURS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def init_db() -> None:
    """Bot start hone par tables bana deta hai (agar pehle se nahi hain)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                first_name     TEXT,
                balance        REAL NOT NULL DEFAULT 0,
                referred_by    INTEGER,
                referral_count INTEGER NOT NULL DEFAULT 0,
                last_bonus_at  TEXT,
                is_banned      INTEGER NOT NULL DEFAULT 0,
                joined_at      TEXT NOT NULL
            )
        """)
        # Har paise ki entry ka record (audit ke liye zaroori)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                amount     REAL NOT NULL,
                kind       TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def get_user(user_id: int):
    """User ki row dict ki tarah return karta hai, na mile to None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def register_user(user_id, username, first_name, referrer_id=None):
    """
    Naya user register karta hai.
    Return: (is_new, valid_referrer_id)
    Guards: khud ko refer nahi kar sakte, purana user dobara count nahi hoga.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        valid_ref = None
        if referrer_id and referrer_id != user_id:
            cur = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?", (referrer_id,))
            if await cur.fetchone():
                valid_ref = referrer_id

        # INSERT OR IGNORE: user pehle se hai to rowcount 0 aayega
        cur = await db.execute(
            """INSERT OR IGNORE INTO users
               (user_id, username, first_name, balance, referred_by, joined_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, first_name, SIGNUP_BONUS, valid_ref,
             _now().isoformat()),
        )
        if cur.rowcount == 0:
            return False, None

        await db.execute(
            "INSERT INTO transactions (user_id, amount, kind, created_at) "
            "VALUES (?, ?, 'signup_bonus', ?)",
            (user_id, SIGNUP_BONUS, _now().isoformat()))

        if valid_ref:
            await db.execute(
                "UPDATE users SET balance = balance + ?, "
                "referral_count = referral_count + 1 WHERE user_id = ?",
                (REFERRAL_BONUS, valid_ref))
            await db.execute(
                "INSERT INTO transactions (user_id, amount, kind, created_at) "
                "VALUES (?, ?, 'referral_bonus', ?)",
                (valid_ref, REFERRAL_BONUS, _now().isoformat()))

        await db.commit()
        return True, valid_ref


async def claim_daily_bonus(user_id: int):
    """
    Return: (success, hours_left)
    Agar 24 ghante nahi hue to (False, bache_hue_ghante).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT last_bonus_at FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row is None:
            return False, 0

        if row["last_bonus_at"]:
            last = datetime.fromisoformat(row["last_bonus_at"])
            next_time = last + timedelta(hours=DAILY_COOLDOWN_HOURS)
            if _now() < next_time:
                hours_left = (next_time - _now()).total_seconds() / 3600
                return False, hours_left

        await db.execute(
            "UPDATE users SET balance = balance + ?, last_bonus_at = ? "
            "WHERE user_id = ?",
            (DAILY_BONUS, _now().isoformat(), user_id))
        await db.execute(
            "INSERT INTO transactions (user_id, amount, kind, created_at) "
            "VALUES (?, ?, 'daily_bonus', ?)",
            (user_id, DAILY_BONUS, _now().isoformat()))
        await db.commit()
        return True, 0