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
        await db.commit()

async def get_cached_link(original_link: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT final_link, created_at FROM link_cache WHERE original_link = ?",
            (original_link,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                final_link, created_at = row
                if time.time() - created_at < EXPIRATION_SECONDS:
                    return final_link
                else:
                    # Expired, let's delete it
                    await delete_cached_link(original_link)
            return None

async def put_cached_link(original_link: str, final_link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO link_cache (original_link, final_link, created_at) VALUES (?, ?, ?)",
            (original_link, final_link, int(time.time()))
        )
        await db.commit()

async def delete_cached_link(original_link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM link_cache WHERE original_link = ?", (original_link,))
        await db.commit()
