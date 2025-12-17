import aiosqlite
import asyncio
import time

DB_NAME = "bot_data.db"

TIMEOUT = 5.0

async def init_db():
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute("PRAGMA journal_mode=WAL;") 
        
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY, username TEXT UNIQUE)")
        await db.execute("CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER, source_id INTEGER, UNIQUE(user_id, source_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS filters (user_id INTEGER, filter_type TEXT, value TEXT)")
        
        # --- NOTIFICATION QUEUE ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                source TEXT,
                reason TEXT,
                link TEXT
            )
        """)
        
        # --- HISTORY OF SENT MESSAGES  ---
        # to avoid sending duplicates
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sent_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text_content TEXT,
                created_at REAL
            )
        """)
        
        await db.commit()

# --- HISTORY ---
async def add_to_history(user_id, text):
    """
    Add text to the sent history for the user with a timestamp
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute(
            "INSERT INTO sent_history (user_id, text_content, created_at) VALUES (?, ?, ?)",
            (user_id, text, time.time())
        )
        await db.commit()

async def get_user_history(user_id):
    """
    Get texts sent to the user in the last 24 hours
    """
    cutoff = time.time() - 86400
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        async with db.execute("SELECT text_content FROM sent_history WHERE user_id=? AND created_at > ?", (user_id, cutoff)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def cleanup_history():
    """
    Delete history entries older than 24 hours
    """
    cutoff = time.time() - 86400
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute("DELETE FROM sent_history WHERE created_at <= ?", (cutoff,))
        await db.commit()

# --- NOTIFICATION QUEUE ---
async def add_notification(user_id, text, source, reason, link):
    """
    Add a notification to the queue
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute(
            "INSERT INTO notification_queue (user_id, text, source, reason, link) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, source, reason, link)
        )
        await db.commit()

async def get_and_clear_notifications():
    """
    Get all notifications from the queue and clear them
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        async with db.execute("SELECT id, user_id, text, source, reason, link FROM notification_queue") as cursor:
            rows = await cursor.fetchall()
        
        if rows:
            ids = [r[0] for r in rows]
            await db.execute(f"DELETE FROM notification_queue WHERE id IN ({','.join(map(str, ids))})")
            await db.commit()
    return rows

# --- BASIC PRACTICES ---

# --- Adding ---
async def add_user(uid):
    """
    Add a new user if not exists
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        await db.commit()

async def add_source(username):
    """
    Add a new source if not exists and return its ID
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute("INSERT OR IGNORE INTO sources (username) VALUES (?)", (username,))
        await db.commit()
        async with db.execute("SELECT id FROM sources WHERE username = ?", (username,)) as cursor:
            return (await cursor.fetchone())[0]

async def subscribe_user(uid, sid):
    """
    Subscribe a user to a source
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute("INSERT OR IGNORE INTO subscriptions (user_id, source_id) VALUES (?, ?)", (uid, sid))
        await db.commit()

async def add_filter(uid, ft, val):
    """
    Add a filter for a user
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        cursor = await db.execute("SELECT 1 FROM filters WHERE user_id=? AND filter_type=? AND value=?", (uid, ft, val))
        if not await cursor.fetchone():
            await db.execute("INSERT INTO filters (user_id, filter_type, value) VALUES (?, ?, ?)", (uid, ft, val))
            await db.commit()

# --- Removing ---
async def remove_subscription(user_id, channel_name):
    """
    Remove a subscription for a user
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        cursor = await db.execute("SELECT id FROM sources WHERE username=?", (channel_name,))
        row = await cursor.fetchone()
        if not row: return False
        source_id = row[0]
        await db.execute("DELETE FROM subscriptions WHERE user_id=? AND source_id=?", (user_id, source_id))
        await db.commit()
        return True

async def remove_filter(user_id, f_type, value):
    """
    Remove a filter for a user
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute("DELETE FROM filters WHERE user_id=? AND filter_type=? AND value=?", (user_id, f_type, value))
        await db.commit()

async def clear_all_data(user_id):
    """
    Clear all stored data for a user
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        await db.execute("DELETE FROM subscriptions WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM filters WHERE user_id=?", (user_id,))
        await db.commit()

# --- Fetching ---
async def get_users_for_source(username):
    """
    Get all user IDs subscribed to a specific source
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        res = await db.execute_fetchall("SELECT s.user_id FROM subscriptions s JOIN sources src ON s.source_id=src.id WHERE src.username=?", (username,))
        return [r[0] for r in res]

async def get_user_filters(uid):
    """
    Get all filters for a user
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        return await db.execute_fetchall("SELECT filter_type, value FROM filters WHERE user_id=?", (uid,))

async def get_user_subscriptions_names(uid):
    """
    Get all source names subscribed to by a user
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        res = await db.execute_fetchall("SELECT src.username FROM subscriptions s JOIN sources src ON s.source_id=src.id WHERE s.user_id=?", (uid,))
        return [r[0] for r in res]
    
async def get_all_sources():
    """
    Get all source usernames
    """
    async with aiosqlite.connect(DB_NAME, timeout=TIMEOUT) as db:
        res = await db.execute_fetchall("SELECT username FROM sources")
        return [r[0] for r in res]