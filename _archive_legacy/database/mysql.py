"""V1.4 MySQL 数据库连接。

连接信息一律从 .env 读取（MYSQL_HOST / MYSQL_PORT / MYSQL_USER /
MYSQL_PASSWORD / MYSQL_DATABASE），不硬编码任何凭据。
create_engine 为惰性连接，仅 import 不会触发真实连接。
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


def database_url() -> str:
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    name = os.getenv("MYSQL_DATABASE", "hedgefund")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"


engine = create_engine(database_url())


def get_connection():
    return engine.connect()
