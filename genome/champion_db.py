"""V1.3 策略历史数据库：SQLite 记录每次上线的冠军策略。"""

import sqlite3


class ChampionDB:
    """冠军策略历史数据库。

    表 ``champions(strategy TEXT, score REAL, date TEXT)``，
    用于留存每次“策略冠军上线”的历史（研究/模拟用途）。
    """

    def __init__(self, db_path: str = "champion.db") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS champions
            (
                strategy TEXT,
                score REAL,
                date TEXT
            )
            """
        )
        self.conn.commit()

    def save(self, strategy: str, score: float, date: str) -> None:
        """保存一条冠军记录。"""
        self.conn.execute(
            """
            INSERT INTO champions
            VALUES(?,?,?)
            """,
            (strategy, score, date),
        )
        self.conn.commit()

    def all(self) -> list:
        """返回全部冠军记录。"""
        cur = self.conn.execute("SELECT strategy, score, date FROM champions")
        return [
            {"strategy": r[0], "score": r[1], "date": r[2]} for r in cur.fetchall()
        ]

    def close(self) -> None:
        """关闭数据库连接。"""
        self.conn.close()
