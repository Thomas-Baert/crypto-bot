import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "crypto_bot.db")

STARTING_BALANCE = 100.0

async def init_db():
    """Initialise la base de données et crée les tables si elles n'existent pas."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 100.0,
                last_daily TEXT DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                user_id TEXT,
                crypto_id TEXT,
                amount REAL DEFAULT 0.0,
                PRIMARY KEY (user_id, crypto_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lilian_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                amount REAL,
                bet_type TEXT,
                val1 REAL,
                val2 REAL
            )
        """)
        await db.commit()


async def get_or_create_user(user_id: str, username: str) -> dict:
    """Récupère ou crée un utilisateur avec son solde de départ."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (str(user_id),)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            else:
                await db.execute(
                    "INSERT INTO users (user_id, username, balance, last_daily) VALUES (?, ?, ?, NULL)",
                    (str(user_id), username, STARTING_BALANCE),
                )
                await db.commit()
                return {
                    "user_id": str(user_id),
                    "username": username,
                    "balance": STARTING_BALANCE,
                    "last_daily": None,
                }


async def update_balance(user_id: str, new_balance: float):
    """Met à jour le solde d'un utilisateur."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (new_balance, str(user_id)),
        )
        await db.commit()


async def update_last_daily(user_id: str, timestamp: str):
    """Met à jour la date du dernier /daily."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_daily = ? WHERE user_id = ?",
            (timestamp, str(user_id)),
        )
        await db.commit()


async def get_holdings(user_id: str) -> list[dict]:
    """Récupère tous les holdings d'un utilisateur (quantité > 0)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT crypto_id, amount FROM holdings WHERE user_id = ? AND amount > 0",
            (str(user_id),),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_holding(user_id: str, crypto_id: str) -> float:
    """Récupère la quantité d'une crypto spécifique pour un utilisateur."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT amount FROM holdings WHERE user_id = ? AND crypto_id = ?",
            (str(user_id), crypto_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0


async def update_holding(user_id: str, crypto_id: str, new_amount: float):
    """Met à jour ou crée un holding pour un utilisateur."""
    async with aiosqlite.connect(DB_PATH) as db:
        if new_amount <= 0:
            await db.execute(
                "DELETE FROM holdings WHERE user_id = ? AND crypto_id = ?",
                (str(user_id), crypto_id),
            )
        else:
            await db.execute(
                """
                INSERT INTO holdings (user_id, crypto_id, amount)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, crypto_id) DO UPDATE SET amount = excluded.amount
                """,
                (str(user_id), crypto_id, new_amount),
            )
        await db.commit()


async def get_all_users() -> list[dict]:
    """Récupère tous les utilisateurs (pour le leaderboard)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, balance FROM users"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_all_holdings() -> list[dict]:
    """Récupère tous les holdings de tous les utilisateurs (pour le leaderboard)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, crypto_id, amount FROM holdings WHERE amount > 0"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def place_lilian_bet(user_id: str, amount: float, bet_type: str, val1: float, val2: float = None):
    """Enregistre un pari sur la note de Lilian."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO lilian_bets (user_id, amount, bet_type, val1, val2)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(user_id), amount, bet_type, val1, val2),
        )
        await db.commit()


async def get_all_lilian_bets() -> list[dict]:
    """Récupère tous les paris en cours."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM lilian_bets") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def clear_lilian_bets():
    """Supprime tous les paris une fois la note résolue."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM lilian_bets")
        await db.commit()
