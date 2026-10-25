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


class LedgerRepository:

    @staticmethod
    async def log_ledger_entry(reference: str, email: str, gross_amount: float, fee: float, net_balance: float):
        await db_execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                gross_amount REAL NOT NULL,
                fee REAL NOT NULL,
                net_balance REAL NOT NULL,
                status TEXT DEFAULT 'HELD',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        query = """
            INSERT OR REPLACE INTO ledger (reference, email, gross_amount, fee, net_balance, status)
            VALUES (?, ?, ?, ?, ?, 'HELD')
        """
        return await db_execute(query, (reference, email, gross_amount, fee, net_balance))

    @staticmethod
    async def get_ledger_summary():
        try:
            query = "SELECT SUM(gross_amount) as total_gross, SUM(fee) as total_fees, SUM(net_balance) as total_net, status FROM ledger GROUP BY status"
            rows = await db_execute(query)
            return rows if isinstance(rows, list) else []
        except Exception:
            return []

    @staticmethod
    async def get_all_ledger_entries(limit: int = 50):
        try:
            query = "SELECT reference, email, gross_amount, fee, net_balance, status, created_at FROM ledger ORDER BY id DESC LIMIT ?"
            rows = await db_execute(query, (limit,))
            return rows if isinstance(rows, list) else []
        except Exception:
            return []
