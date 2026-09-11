"""AI Hedge Fund OS V1.8 主程序：真实 A 股历史数据 → 因子工程 → 训练数据。

研究/模拟用途，不连接任何实盘交易接口。
"""

from data_engine.akshare_loader import AkShareLoader
from dataset.feature_pipeline import FeaturePipeline

stocks = ["600519", "300394", "688568"]

loader = AkShareLoader()
data = loader.load_batch(stocks)

pipeline = FeaturePipeline()
for code, df in data.items():
    factor = pipeline.transform(df)
    print(code, factor.tail())

print("AI训练数据准备完成")
