"""V2.2 自动任务调度系统：每天定时执行市场扫描 / 收盘复盘。"""

from apscheduler.schedulers.blocking import BlockingScheduler


class AIScheduler:
    """AI 定时调度器。"""

    def __init__(self):
        self.scheduler = BlockingScheduler()

    def add_daily_task(self, func, hour, minute) -> None:
        """注册每日定时任务。

        Args:
            func: 任务函数。
            hour: 小时。
            minute: 分钟。
        """
        self.scheduler.add_job(func, "cron", hour=hour, minute=minute)

    def start(self) -> None:
        """启动调度器（阻塞）。"""
        self.scheduler.start()
