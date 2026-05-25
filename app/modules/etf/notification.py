from __future__ import annotations

import asyncio
import html
import smtplib
from email.message import EmailMessage

from app.core.config import settings


def build_strategy_email(code: str, stage: int, price: float, retract: float) -> tuple[str, str]:
    subject = "【量化策略】观察点到达提示"
    safe_code = html.escape(code)
    body = f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{ margin: 0; background: #f6f7f9; color: #1f2937; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 560px; margin: 0 auto; padding: 24px 16px; }}
    .panel {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; }}
    .title {{ margin: 0 0 12px; font-size: 18px; font-weight: 700; }}
    .text {{ margin: 0 0 16px; line-height: 1.7; font-size: 14px; }}
    .grid {{ display: grid; gap: 10px; }}
    .item {{ padding: 12px; background: #f9fafb; border-radius: 6px; }}
    .label {{ color: #6b7280; font-size: 12px; }}
    .value {{ margin-top: 4px; font-size: 16px; font-weight: 700; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1 class="title">观察点到达提示</h1>
      <p class="text">您关注的标的（{safe_code}）已触及预设的第 {stage} 级技术观察点，当前偏离度为 {retract:.2%}，特此提示。</p>
      <div class="grid">
        <div class="item"><div class="label">标的代码</div><div class="value">{safe_code}</div></div>
        <div class="item"><div class="label">当前价格</div><div class="value">{price:.4f}</div></div>
        <div class="item"><div class="label">当前偏离度</div><div class="value">{retract:.2%}</div></div>
      </div>
    </div>
  </div>
</body>
</html>
"""
    return subject, body


def _send_email(subject: str, body: str) -> None:
    if not all([settings.smtp_host, settings.smtp_from, settings.smtp_to]):
        raise RuntimeError("SMTP_HOST, SMTP_FROM and SMTP_TO are required for email notification.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.smtp_to
    message.set_content("观察点到达提示，请使用支持 HTML 的客户端查看。")
    message.add_alternative(body, subtype="html")

    if settings.smtp_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)


async def send_strategy_notification(code: str, stage: int, price: float, retract: float) -> None:
    subject, body = build_strategy_email(code, stage, price, retract)
    await asyncio.to_thread(_send_email, subject, body)
