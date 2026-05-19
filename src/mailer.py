import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def send_report_email(to_email: str, report_html: str, subject: Optional[str] = None) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env")

    if subject is None:
        subject = "ValCoach - 你的赛后诊断报告"

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    text_part = MIMEText("请使用支持HTML的邮件客户端查看此报告。", "plain", "utf-8")
    html_part = MIMEText(report_html, "html", "utf-8")

    msg.attach(text_part)
    msg.attach(html_part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to send email: {str(e)}")
