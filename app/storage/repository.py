from app.storage.database import db_execute

class LedgerRepository:

    @staticmethod
    async def log_ledger_entry(reference: str, email: str, gross_amount: float, fee: float, net_balance: float):
        # Ensure ledger table exists
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
