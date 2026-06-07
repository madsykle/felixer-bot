import aiosqlite
import time

DB_PATH = "bypassed_links.db"
EXPIRATION_SECONDS = 30 * 24 * 60 * 60  # 30 days

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS link_cache (
                original_link TEXT PRIMARY KEY,
                final_link TEXT,
                created_at INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS unique_users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY (user_id, key)
            )
        """)
        await db.commit()

async def get_cached_link(original_link: str) -> str | None:
    return None

async def put_cached_link(original_link: str, final_link: str):
    pass

async def delete_cached_link(original_link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM link_cache WHERE original_link = ?", (original_link,))
        await db.commit()

async def increment_stat(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_stats (key, value) VALUES (?, 1) "
            "ON CONFLICT(key) DO UPDATE SET value = value + 1",
            (key,)
        )
        await db.commit()

async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO unique_users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()

async def get_all_stats() -> dict:
    stats = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM bot_stats") as cursor:
            async for row in cursor:
                stats[row[0]] = row[1]
        async with db.execute("SELECT COUNT(*) FROM unique_users") as cursor:
            row = await cursor.fetchone()
            stats['users'] = row[0] if row else 0
    return stats

async def get_user_setting(user_id: int, key: str, default: str = "Ask") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
            (user_id, key)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return default

async def set_user_setting(user_id: int, key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_settings (user_id, key, value) VALUES (?, ?, ?)",
            (user_id, key, value)
        )
        await db.commit()
