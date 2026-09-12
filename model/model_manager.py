"""V2.7 模型管理系统：注册与获取模型。"""


class ModelManager:
    """模型注册中心。"""

    def __init__(self):
        self.models = {}

    def add(self, name, model):
        self.models[name] = model

    def get(self, name):
        return self.models.get(name)
