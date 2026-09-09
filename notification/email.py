"""V1.4 邮件推送。

SMTP 配置（SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_TO）
一律从 .env 读取；未配置时仅打印“邮件发送成功(模拟)”，不发送真实邮件。
"""

import os
import smtplib
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()


def send_email(content: str, subject: str = "AI基金日报") -> str:
    """发送日报邮件；未配置 SMTP 时返回 SIMULATED。"""
    msg = MIMEText(content)
    msg["Subject"] = subject
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    to_addr = os.getenv("SMTP_TO", "")
    if not (smtp_host and smtp_user and smtp_password and to_addr):
        print("邮件发送成功(模拟)")
        return "SIMULATED"
    msg["From"] = smtp_user
    msg["To"] = to_addr
    server = smtplib.SMTP_SSL(smtp_host, smtp_port)
    try:
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
    finally:
        server.quit()
    return "SENT"
