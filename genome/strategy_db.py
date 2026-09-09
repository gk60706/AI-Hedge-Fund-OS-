"""V1.2 策略基因数据库：SQLite 持久化策略（名称/分数/代码）。"""

import sqlite3


class StrategyDB:
    """策略基因数据库。

    使用 SQLite 存储进化后的策略：
    表 ``strategy(name TEXT, score REAL, code TEXT)``。
    """

    def __init__(self, db_path: str = "strategy.db") -> None:
        self.conn = sqlite3.connect(db_path)
        self.create()

    def create(self) -> None:
        """创建策略表（若不存在）。"""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy
            (
                name TEXT,
                score REAL,
                code TEXT
            )
            """
        )
        self.conn.commit()

    def save(self, strategy: dict) -> None:
        """保存一条策略记录。"""
        self.conn.execute(
            """
            INSERT INTO strategy
            VALUES(?,?,?)
            """,
            (
                strategy["name"],
                strategy["score"],
                strategy["code"],
            ),
        )
        self.conn.commit()

    def all(self) -> list:
        """返回全部策略记录列表。"""
        cur = self.conn.execute("SELECT name, score, code FROM strategy")
        return [
            {"name": row[0], "score": row[1], "code": row[2]} for row in cur.fetchall()
        ]

    def close(self) -> None:
        """关闭数据库连接。"""
        self.conn.close()
