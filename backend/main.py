from __future__ import annotations

import argparse
import sys

from fastapi import FastAPI, HTTPException

from agents.workflow import run_agent_research, run_research
from pipeline.fundamental_pipeline import run_ai_selection
from scanners.scanner import scan_market
from tools.market_tool import MarketDataError, get_a_share_quote

app = FastAPI(
    title="AI Hedge Fund OS",
    version="0.4.0",
    description="AI 股票研究与量化基础设施（研究/模拟用途，禁止实盘交易）",
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "ai-hedge-fund-os",
        "version": "0.4.0",
    }


@app.get("/api/v1/market/{code}")
def market(code: str) -> dict:
    try:
        return get_a_share_quote(code)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/research/{code}")
def research(code: str) -> dict:
    try:
        return run_research(code)
    except (MarketDataError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/research-agents/{code}")
def research_agents(code: str) -> dict:
    """V0.2 多 Agent 研究：Research/Quant/Risk 综合决策。"""
    try:
        result = run_agent_research(code)
        return {
            "stock": result["stock"],
            "results": result["results"],
            "decision": result["decision"],
        }
    except (MarketDataError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/scan")
def scan(top_n: int = 50) -> dict:
    """V0.3 全市场扫描：主力资金评分 → 机会排序（重负载接口）。"""
    try:
        result = scan_market(top_n=top_n)
        return {"count": len(result), "stocks": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/ai-selection")
def ai_selection() -> dict:
    """V0.4 AI 选股流水线：机会池 → 基本面研究 → 排序。"""
    try:
        result = run_ai_selection()
        return {"count": len(result), "stocks": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/v1/trade")
def trade(signal: dict) -> dict:
    """V0.7 模拟交易：信号 → 模拟订单 → PaperBroker 成交（不接实盘）。"""
    from trading.execution import execute_trade

    try:
        return execute_trade(signal)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def main():
    parser = argparse.ArgumentParser(description="AI Hedge Fund OS CLI")
    parser.add_argument("--code", default="300394", help="A股股票代码，例如300394")
    args = parser.parse_args()
    try:
        result = run_research(args.code)
    except MarketDataError as exc:
        print(
            f"行情获取失败（数据源可能临时限流，请稍后重试或检查网络）: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    print(result["report"])
    if result.get("report_path"):
        print(f"\n报告已保存: {result['report_path']}")


if __name__ == "__main__":
    main()
