from __future__ import annotations

import argparse
import sys

from fastapi import FastAPI, HTTPException

from agents.workflow import run_research
from tools.market_tool import MarketDataError, get_a_share_quote

app = FastAPI(
    title="AI Hedge Fund OS",
    version="0.1.0",
    description="AI 股票研究与量化基础设施 MVP（研究/模拟用途）",
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "ai-hedge-fund-os",
        "version": "0.1.0",
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
