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
        query = "SELECT * FROM intents ORDER BY created_at DESC LIMIT ?"
        return await db_execute(query, (limit,))

class TransactionRepository:
    @staticmethod
    async def save_transaction(reference: str, email: str, amount: float, status: str, playbook_id: str):
        query = """
            INSERT OR IGNORE INTO transactions (reference, email, amount, status, playbook_id)
            VALUES (?, ?, ?, ?, ?)
        """
        return await db_execute(query, (reference, email, amount, status, playbook_id))
