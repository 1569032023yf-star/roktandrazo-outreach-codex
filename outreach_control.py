"""Pure, testable controls for city outreach planning.

This module intentionally does not import project database or sender modules.
It is safe to import in tests and migration verification.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    SHANGHAI = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    # Windows/Python installations without tzdata still need Shanghai's fixed UTC+8 business clock.
    SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
NEW_OUTREACH_TARGET = 40
FOLLOW_UP_MAX = 5
# ── P2.3P: follow-up 生产开关 ──
# 镜像 bd_execution_host_service.CURRENT_SEND_POLICY["follow_up_enabled"]
# （后者是服务内常量，bd_orchestrator 不能直接 import 它，否则会拉起 win32service 运行时，
#  故在此处维护同值副本；改值必须同步两边）。
# False = 生产 PreSend 不得创建任何 message_type='follow_up' 的 FSP。
# 历史 follow-up 代码与数据全部保留，只是生产当前不使用。
FOLLOW_UP_ENABLED = False
INVENTORY_TARGET = 30  # weekday sendable orgs target
INVENTORY_WARNING_THRESHOLD = 20
INVENTORY_CRITICAL_THRESHOLD = 10
SEND_START = time(23, 0)
SEND_STOP_NEW_REQUESTS = time(23, 59, 30)
MIN_SEND_DELAY_SECONDS = 45
MAX_SEND_DELAY_SECONDS = 85

RETAIL_QUERY_FAMILIES = (
    "toy store", "board game store", "game store", "tabletop game store",
    "gift shop", "independent gift store", "museum gift shop", "bookstore",
    "independent bookstore", "comic book store", "hobby store",
    "educational supply store", "teacher supply store", "children's store",
    "family game store", "visitor center gift shop", "tourist gift shop",
    "specialty retailer", "puzzle store", "card game store",
)
RETAIL_SOURCES = (
    "google_places", "serpapi_maps", "mock",
    "Search Engine", "Maps / Local Listing", "Chamber of Commerce",
    "Tourism / Visitor Directory", "Museum / Institution Directory",
    "Official Website", "Facebook Enrichment",
)
DEFAULT_RETAIL_CITIES = (
    ("Nashville", "TN", 1, "America/Chicago"),
    ("Memphis", "TN", 2, "America/Chicago"),
    ("Knoxville", "TN", 3, "America/New_York"),
    ("Little Rock", "AR", 10, "America/Chicago"),
    ("Fayetteville", "AR", 11, "America/Chicago"),
    ("Louisville", "KY", 20, "America/New_York"),
    ("Lexington", "KY", 21, "America/New_York"),
)


def shanghai_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(SHANGHAI)
    return now.astimezone(SHANGHAI) if now.tzinfo else now.replace(tzinfo=SHANGHAI)


def outreach_batch_date(now: datetime | None = None) -> str:
    """Return the 23:00 batch date; shortly-after-midnight work stays with last night."""
    current = shanghai_now(now)
    if current.time() < time(1, 0):
        current -= timedelta(days=1)
    return current.date().isoformat()


def inventory_target_for_date(business_date: str) -> int:
    """Inventory 累积目标：工作日 30，周末（周六/周日）缓冲 60。

    business_date 是 Asia/Shanghai 业务日期（ISO 字符串），本地 naive date 的
    weekday() 即 Mon=0 … Sun=6。周末补库存缓冲，确保周一发送窗口有充足库存。
    解析失败 fail-safe 回退到工作日目标 30。
    """
    try:
        d = datetime.fromisoformat(str(business_date)).date()
    except (ValueError, TypeError):
        return INVENTORY_TARGET
    return 60 if d.weekday() >= 5 else INVENTORY_TARGET


def may_start_smtp_request(now: datetime | None = None) -> bool:
    current = shanghai_now(now).time()
    return SEND_START <= current <= SEND_STOP_NEW_REQUESTS


def is_strict_a0(lead: dict) -> bool:
    return (
        lead.get("status") == "new"
        and lead.get("confidence_score") == "A"
        and bool(lead.get("auto_sendable"))
        and bool(lead.get("email_verified_on_official_site"))
        and lead.get("email_source_type") in {
            "official_page_visible", "official_mailto", "wholesale_vendor_page"
        }
        and bool(lead.get("email"))
        and bool(lead.get("evidence_url"))
        and bool(lead.get("evidence_snippet"))
        and not lead.get("unsubscribed_at")
    )


def build_final_plan_entries(leads: list[dict], batch_date: str, message_type: str,
                             eligible_check: callable | None = None) -> list[dict]:
    """Freeze only already-approved inputs; callers supply rendered subject/body.

    eligible_check: 可选 callable(lead: dict) -> bool。正式政策下 new_outreach
    的资格由调用方注入（Campaign Eligible 判定）；缺省回退 is_strict_a0 仅作
    字段级兜底（历史行为），不再把 Strict A0 当作唯一发送池。
    """
    if message_type not in {"new_outreach", "follow_up"}:
        raise ValueError("unsupported message_type")
    limit = NEW_OUTREACH_TARGET if message_type == "new_outreach" else FOLLOW_UP_MAX
    entries = []
    for sequence, lead in enumerate(leads[:limit], start=1):
        if message_type == "new_outreach":
            if eligible_check is not None:
                if not eligible_check(lead):
                    continue
            elif not is_strict_a0(lead):
                continue
        required = ("id", "email", "store_name", "email_subject", "email_body", "evidence_url")
        if any(not lead.get(field) for field in required):
            continue
        entries.append({
            "lead_id": lead["id"], "recipient_email": lead["email"].strip().lower(),
            "company_name": lead["store_name"], "customer_type": lead.get("customer_type") or lead.get("store_type") or "retail",
            "lead_segment": lead.get("lead_segment") or "strict_a0",
            # template_id 兼容旧字段：优先 template_key（P0 渲染元数据），preflight 用它校验模板注册
            "template_id": lead.get("template_id") or lead.get("template_key") or "",
            "source_city": lead.get("city") or "",
            "source_state": lead.get("state") or "", "evidence_url": lead["evidence_url"],
            "hygiene_passed_at": lead.get("hygiene_passed_at") or datetime.now(SHANGHAI).isoformat(),
            "message_type": message_type, "outreach_batch_date": batch_date,
            "planned_sequence": sequence, "subject": lead["email_subject"],
            "body_text": lead["email_body"], "body_html": lead.get("email_body_html") or "",
        })
    return entries


def all_city_completion_conditions_met(checks: dict[str, bool]) -> bool:
    required = {
        "all_query_families", "all_sources_or_reasons", "pagination_complete",
        "two_empty_pages", "all_candidates_classified", "no_unprocessed_candidates",
        "official_site_recheck", "review_recovery", "last_three_batches_empty",
    }
    return required.issubset(checks) and all(checks[key] for key in required)
