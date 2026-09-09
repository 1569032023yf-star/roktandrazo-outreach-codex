import os as _dev_os
if _dev_os.path.exists(_dev_os.path.join(_dev_os.path.dirname(__file__), ".development-copy")):
    from development_safety import install as _install_development_safety
    _install_development_safety()

# ══ P0 HARD-DISABLED: Production SMTP blocked ══
class LegacySMTPDisabledError(Exception): pass
import os as _os
if not _os.environ.get('BD_TEST_MODE')=='true':
    raise LegacySMTPDisabledError('Legacy SMTP disabled. Use bd_orchestrator with valid authorization.')
"""
Roktandrazo Outreach - Email Sender
SMTP 发送邮件，支持每日限额、间隔控制、发信窗口
"""

import smtplib
import time
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SENDER_EMAIL, SENDER_NAME, SENDER_TITLE,
    MAX_EMAILS_PER_DAY, MIN_DELAY_BETWEEN_SECONDS,
    EMAIL_DAILY_SEND_WINDOW,
)
from db import get_db, update_email_status, update_lead_status, insert_email


# 美东时区
ET = timezone(timedelta(hours=-4))

LEGACY_LIVE_DISABLED_MESSAGE = (
    "LEGACY_LIVE_DISABLED: legacy live sending is disabled. "
    "Use bd_sender.py/daily_operator_auto.py controlled workflow only."
)


def _legacy_live_disabled_result(to_email: str = "") -> dict:
    target = f" for {to_email}" if to_email else ""
    return {
        "success": False,
        "message": LEGACY_LIVE_DISABLED_MESSAGE,
        "email_id": None,
    }


def _is_within_send_window() -> bool:
    """检查当前是否在发信窗口内 (美东时间 9am-5pm)"""
    now_et = datetime.now(ET)
    start = EMAIL_DAILY_SEND_WINDOW["start_hour"]
    end = EMAIL_DAILY_SEND_WINDOW["end_hour"]
    # 周末不发
    if now_et.weekday() >= 5:
        return False
    return start <= now_et.hour < end


def _get_daily_send_count() -> int:
    """获取今天已发送的邮件数量"""
    conn = get_db()
    c = conn.cursor()
    today_start = datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0)
    c.execute("""
    SELECT COUNT(*) FROM emails 
    WHERE status = 'sent' 
    AND sent_at >= ?
    """, (today_start.isoformat(),))
    count = c.fetchone()[0]
    conn.close()
    return count


def _send_email_smtp(to_email: str, subject: str, body_text: str, body_html: str = None) -> tuple[bool, str]:
    """通过 SMTP 发送邮件"""
    return False, LEGACY_LIVE_DISABLED_MESSAGE

    if not SMTP_USER or not SMTP_PASSWORD:
        return False, "SMTP credentials not configured"

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL or SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body_text, "plain"))

    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL or SMTP_USER, to_email, msg.as_string())
        return True, "Sent successfully"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed — check credentials"
    except smtplib.SMTPRecipientsRefused as e:
        return False, f"Recipient refused: {e}"
    except Exception as e:
        return False, f"SMTP error: {str(e)}"


def send_email_to_lead(lead: dict, email_draft: dict, dry_run: bool = True, force_send: bool = False) -> dict:
    """
    给线索发送邮件
    
    Args:
        lead: 线索数据
        email_draft: 邮件草稿 (from drafter)
        dry_run: True = 只记录不发，False = 实际发送
    
    Returns:
        dict with success, message, email_id
    """
    # 检查前提条件
    to_email = lead.get("email", "")
    if not to_email or to_email.strip() == "":
        return {"success": False, "message": "No email address", "email_id": None}

    if lead.get("status") in ["do_not_contact", "unsubscribed", "bounced"]:
        return {"success": False, "message": f"Lead status is {lead.get('status')}", "email_id": None}

    if dry_run:
        return {
            "success": True,
            "message": "[DRY RUN READ-ONLY] Email preview prepared",
            "email_id": None,
        }

    return _legacy_live_disabled_result(to_email)

    # 记录邮件到数据库
    email_id = insert_email(
        lead_id=lead["id"],
        email_type=email_draft.get("email_type", "initial"),
        subject=email_draft.get("subject", ""),
        body_text=email_draft.get("body_text", ""),
        body_html=email_draft.get("body_html", ""),
    )

    if dry_run:
        update_email_status(email_id, "draft")
        return {
            "success": True,
            "message": f"[DRY RUN] Email drafted for {to_email}",
            "email_id": email_id,
        }

    # 实际发送
    # 检查发信窗口 (除非 force_send=True)
    if not force_send and not _is_within_send_window():
        update_email_status(email_id, "queued")
        return {
            "success": True,
            "message": f"Outside send window — queued for {to_email}",
            "email_id": email_id,
        }

    # 检查每日限额
    daily_count = _get_daily_send_count()
    if daily_count >= MAX_EMAILS_PER_DAY:
        update_email_status(email_id, "queued")
        return {
            "success": True,
            "message": f"Daily limit ({MAX_EMAILS_PER_DAY}) reached — queued for {to_email}",
            "email_id": email_id,
        }

    # 发送
    success, message = _send_email_smtp(
        to_email=to_email,
        subject=email_draft.get("subject", ""),
        body_text=email_draft.get("body_text", ""),
        body_html=email_draft.get("body_html"),
    )

    if success:
        update_email_status(email_id, "sent")
        update_lead_status(lead["id"], "sent", f"Initial email sent at {datetime.now().isoformat()}")
    else:
        if "refused" in message.lower() or "bounce" in message.lower():
            update_email_status(email_id, "bounced", message)
            update_lead_status(lead["id"], "bounced", message)
        else:
            update_email_status(email_id, "failed", message)

    return {
        "success": success,
        "message": message,
        "email_id": email_id,
    }


def batch_send(leads_with_drafts: list[tuple[dict, dict]], dry_run: bool = True) -> list[dict]:
    """
    批量发送邮件
    
    Args:
        leads_with_drafts: [(lead, email_draft), ...]
        dry_run: True = 只记录不发
    
    Returns:
        list of send results
    """
    results = []
    for lead, draft in leads_with_drafts:
        result = send_email_to_lead(lead, draft, dry_run=dry_run)
        results.append(result)
        if not dry_run and result["success"]:
            time.sleep(MIN_DELAY_BETWEEN_SECONDS)
    return results


if __name__ == "__main__":
    # 测试
    print("=== Email Sender 模块 ===")
    print(f"SMTP: {SMTP_HOST}:{SMTP_PORT}")
    print(f"发信窗口 (美东): {EMAIL_DAILY_SEND_WINDOW['start_hour']}am - {EMAIL_DAILY_SEND_WINDOW['end_hour']}pm")
    print(f"每日限额: {MAX_EMAILS_PER_DAY} 封")
    print(f"发信间隔: {MIN_DELAY_BETWEEN_SECONDS} 秒")
    print()
    
    is_window = _is_within_send_window()
    print(f"当前在发信窗口内: {is_window}")
    
    if not SMTP_USER:
        print("\n⚠️  SMTP 未配置 — 需要设置 SMTP_USER 和 SMTP_PASSWORD")
        print("   在 config.py 中填写 Gmail App Password 或其他 SMTP 凭证")
