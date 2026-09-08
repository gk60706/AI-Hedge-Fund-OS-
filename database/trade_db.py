"""交易记录数据库 (V0.7)

SQLite 持久化模拟成交记录。
"""
import sqlite3


class TradeDB:
    """交易记录数据库。"""

    def __init__(self, db_path: str = "trade.db"):
        self.conn = sqlite3.connect(db_path)
        self.create()

    def create(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS trades(
        id INTEGER PRIMARY KEY,
        code TEXT,
        action TEXT,
        price REAL,
        volume INTEGER,
        time TEXT
        )
        """
        self.conn.execute(sql)
        self.conn.commit()

    def insert(self, trade: dict) -> None:
        self.conn.execute(
            """
        INSERT INTO trades
        (code,action,price,volume,time)
        VALUES(?,?,?,?,?)
        """,
            (
                trade["code"],
                trade["action"],
                trade["price"],
                trade["volume"],
                trade["time"],
            ),
        )
        self.conn.commit()
