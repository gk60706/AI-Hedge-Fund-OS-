"""V1.4 定时任务：每日 8:30 股票扫描，15:30 AI 复盘。"""

from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()


@scheduler.scheduled_job("cron", hour=8, minute=30)
def morning_scan():
    print("开始AI股票扫描")


@scheduler.scheduled_job("cron", hour=15, minute=30)
def daily_review():
    print("开始AI复盘")
