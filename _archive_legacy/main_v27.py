"""V2.7 机器学习 Alpha 预测引擎主流程（Alpha 评分演示）。"""

from alpha.alpha_generator import AlphaGenerator

generator = AlphaGenerator()
alpha = generator.generate(xgb=0.85, lstm=0.75, capital=0.9)
print("AI Alpha评分:", alpha)
if alpha > 0.8:
    print("进入AI精选股票池")
