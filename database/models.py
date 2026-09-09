"""V1.4 数据库 ORM 模型：股票主数据表。"""

from sqlalchemy import Column, Float, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Stock(Base):
    __tablename__ = "stocks"

    code = Column(String, primary_key=True)
    price = Column(Float)
    score = Column(Float)
