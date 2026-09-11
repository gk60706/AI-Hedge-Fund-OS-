"""V2.6 组合优化与资金管理主流程（AI 组合 + 资金配置演示）。"""

from portfolio_ai.optimizer import PortfolioOptimizer
from portfolio_ai.asset_allocator import AssetAllocator

stocks = ["300394", "688568", "300750"]

optimizer = PortfolioOptimizer()
portfolio = optimizer.optimize(stocks)
print("AI组合:")
print(portfolio)

allocator = AssetAllocator()
scores = {"300394": 95, "688568": 88, "300750": 75}
print(allocator.allocate(scores))
