"""V1.0 Agent 基础框架：所有 Agent 的抽象基类。"""
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def run(self, data):
        pass
