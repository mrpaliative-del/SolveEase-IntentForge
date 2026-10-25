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


class TransactionRepository:

    @staticmethod
    async def log_transaction(reference: str, task_hash: str, email: str, amount: float, status: str):
        # Ensure transactions table exists
        await db_execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                task_hash TEXT NOT NULL,
                email TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        query = """
            INSERT OR REPLACE INTO transactions (reference, task_hash, email, amount, status)
            VALUES (?, ?, ?, ?, ?)
        """
        return await db_execute(query, (reference, task_hash, email, amount, status))

    @staticmethod
    async def get_transaction(reference: str):
        query = "SELECT * FROM transactions WHERE reference = ?"
        rows = await db_execute(query, (reference,))
        return rows[0] if rows else None
