"""V1.0 晨报系统：生成每日 AI 基金晨报。"""
from datetime import datetime


def morning_report(market, portfolio):
    return f"""
# AI基金晨报

日期: {datetime.now()}
市场: {market}
持仓: {portfolio}
今日计划: AI自动生成

"""
