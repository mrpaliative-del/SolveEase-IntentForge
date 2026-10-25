from app.storage.database import db_execute

class IntentRepository:

    @staticmethod
    async def save_intent(task_hash: str, domain: str, title: str, snippet: str, source: str, price: float):
        query = """
            INSERT OR IGNORE INTO intents (task_hash, domain, title, snippet, source, price)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        return await db_execute(query, (task_hash, domain, title, snippet, source, price))

    @staticmethod
    async def get_latest_intents(limit: int = 50):
        try:
            query = "SELECT task_hash, domain, title, snippet, source, price, created_at FROM intents ORDER BY id DESC LIMIT ?"
            rows = await db_execute(query, (limit,))
            return rows if isinstance(rows, list) else []
        except Exception:
            return []
