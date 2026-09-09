"""Campaign Eligible — Supervised Send 前最终复核模块。

对已经 Broad Ready 的候选，在进入真实发送前做最后一道人工监督复核。
复用的判定：
  - Broad Outreach Ready（broad_ready.is_broad_outreach_ready）
  - 邮件卫生（email_hygiene.hygiene_check）
  - 域名匹配（store-domain 判断）
  - 时区可调度（timezone_status / recipient_timezone）
  - 组织键（organization_key 非空）
  - 历史安全（suppression / bounce / reply / send_log 已在 broad_ready 内检查）

Campaign Eligible 的硬条件（缺一不可）：
  1. broad_ready=True（主池判定）
  2. email 有效且通过 hygiene
  3. 非第三方域名邮箱（store 官网域 != 邮箱域 且无法确认归属 → block）
  4. recipient_timezone 有效（TIMEZONE_UNRESOLVED → block，除非人工 override）
  5. organization_key 非空（用于组织级去重与日报）
  6. 有 evidence（evidence_url 或 evidence_snippet 非空）

输出：{eligible: bool, checks: {name: {pass, detail}}, blockers: [str], campaign_pool: str}
campaign_pool 取值：'CAMPAIGN_ELIGIBLE' / 'NEEDS_MANUAL_REVIEW' / 'BLOCKED'
"""
from __future__ import annotations

import sqlite3
from typing import Any, Mapping, Optional

from email_hygiene import hygiene_check
from broad_ready import is_broad_outreach_ready
from broad_ready import FREE_MAILBOX_DOMAINS, _email_domain


def _domain_of(website: str) -> str:
    if not website:
        return ""
    w = website.strip()
    if not w.startswith("http"):
        w = "https://" + w
    from urllib.parse import urlparse
    try:
        return urlparse(w).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _is_third_party_email(email: str, website: str) -> bool:
    """邮箱域 与 官网域 不一致且邮箱域非免费公共域 → 第三方邮箱（无法确认归属）。"""
    if not email or "@" not in email:
        return True  # 无邮箱 → 视为第三方（不可调度）
    edom = _email_domain(email)
    if edom in FREE_MAILBOX_DOMAINS:
        return False  # 免费邮箱域：归属需要单独 evidence 证明，此处不判为"第三方"但需官方证据
    site_domain = _domain_of(website)
    if not site_domain:
        # 无官网：无法确认归属 → 第三方
        return True
    return not (edom == site_domain or site_domain.endswith("." + edom) or edom.endswith("." + site_domain))


# 官方来源 evidence 判定：仅第一方来源可证明公共邮箱归属。
# 第三方目录（Yelp/Yellow Pages/bizarchive/allbiz/聚合目录）不构成归属证据。
DIRECTORY_HINTS = ("yelp", "yellowpages", "bizarchive", "allbiz", "mapquest", "directory",
                   "chamberofcommerce", "localgamestores", "findglocal", "wanderlog",
                   "n49.com", "go-kentucky", "meetnky", "smallbusinessdb", "keepupcards",
                   "tcgshopfinder", "videogame-stores", "storesinfo", "cmac.ws")
OFFICIAL_EVIDENCE_TYPES = ("official_page_visible", "official_mailto", "wholesale_vendor_page",
                           "web_search_official")


def _is_official_evidence(lead: Mapping[str, Any], email: str, website: str) -> bool:
    """判断邮箱归属证据是否为官方第一方来源。

    满足任一条即视为官方证据：
      1. email_source_type 是官方类型（official_page_visible / official_mailto / ...）
      2. evidence_url 指向官网域名（与 official_website 同域）
      3. store-domain 邮箱（邮箱域 == 官网域）本身即归属证据
    """
    email_src = str(lead.get("email_source_type") or "").lower()
    if email_src in OFFICIAL_EVIDENCE_TYPES:
        return True
    evidence_url = str(lead.get("evidence_url") or "")
    if evidence_url:
        ev_domain = _domain_of(evidence_url)
        site_domain = _domain_of(website)
        if site_domain and ev_domain and (ev_domain == site_domain or ev_domain.endswith("." + site_domain)):
            return True
        # evidence_url 是官网域名（即使 website 字段空，但 evidence 在官网）
        if ev_domain and not any(dh in ev_domain for dh in DIRECTORY_HINTS):
            return True
    # store-domain 邮箱：邮箱域 == 官网域 → 本身就是官方归属证据
    if email and website and "@" in email:
        edom = _email_domain(email)
        site_domain = _domain_of(website)
        if edom and site_domain and (edom == site_domain or site_domain.endswith("." + edom)):
            return True
    return False


def review_campaign_eligible(lead: Mapping[str, Any], ctx: Optional[Mapping[str, Any]] = None) -> dict:
    """对单条 lead 做 Campaign Eligible 复核。

    ctx 可注入：
      conn — sqlite3.Connection（broad_ready 需要）
      allow_timezone_unresolved — bool（默认 False，True 时忽略时区未解析）
    """
    conn = (ctx or {}).get("conn")
    allow_tz = bool((ctx or {}).get("allow_timezone_unresolved"))

    lead_id = lead.get("id")
    store = lead.get("store_name") or ""
    email = lead.get("email") or ""
    website = lead.get("official_website") or ""
    tz_status = lead.get("timezone_status") or "UNSET"
    tz = lead.get("recipient_timezone") or ""
    org_key = lead.get("organization_key") or ""

    checks: dict[str, dict] = {}
    blockers: list[str] = []

    # 1. Broad Ready
    br = is_broad_outreach_ready(lead, ctx) if conn is not None else {"ready": False, "blockers": ["no_conn"]}
    checks["broad_ready"] = {"pass": bool(br.get("ready")), "detail": br.get("blockers") or []}
    if not br.get("ready"):
        blockers.extend([f"broad_ready:{b}" for b in (br.get("blockers") or [])])

    # 2. Hygiene
    h = hygiene_check(email) if email else {"valid": False, "reason": "no_email"}
    checks["hygiene"] = {"pass": bool(h.get("valid")), "detail": h.get("reason", "")}
    if not h.get("valid"):
        blockers.append(f"hygiene:{h.get('reason', 'no_email')}")

    # 3. 第三方域名
    third_party = _is_third_party_email(email, website)
    checks["email_ownership"] = {"pass": not third_party, "detail": f"email={email} website={website}"}
    if third_party:
        blockers.append(f"third_party_email:email domain != official site domain, not free mailbox")

    # 3.5 公共邮箱官方归属证据（ICP V1）
    # 公共邮箱（gmail/yahoo/hotmail/aol/...）本身不是 blocker，
    # 但进入 CAMPAIGN_ELIGIBLE 必须证明"完整邮箱确实属于该商户"。
    # 仅第三方目录证据（Yelp/Yellow Pages/bizarchive/allbiz 等）不构成归属证明。
    edom = _email_domain(email)
    if not third_party and edom in FREE_MAILBOX_DOMAINS:
        official_ev = _is_official_evidence(lead, email, website)
        checks["public_mailbox_ownership"] = {
            "pass": official_ev,
            "detail": f"free mailbox {edom}; official_evidence={'YES' if official_ev else 'NO — directory/similarity only'}",
        }
        if not official_ev:
            blockers.append("public_mailbox_no_official_evidence:free mailbox needs first-party evidence of ownership")

    # 4. 时区
    tz_ok = tz_status == "RESOLVED" and bool(tz)
    if not tz_ok and allow_tz:
        tz_ok = True
        checks["timezone"] = {"pass": True, "detail": f"overridden:{tz_status}/{tz}"}
    else:
        checks["timezone"] = {"pass": tz_ok, "detail": f"{tz_status}/{tz}"}
    if not tz_ok:
        blockers.append(f"timezone:{tz_status}/{tz}")

    # 5. 组织键
    org_ok = bool(org_key.strip())
    checks["organization_key"] = {"pass": org_ok, "detail": org_key or "empty"}
    if not org_ok:
        blockers.append("organization_key_empty")

    # 6. Evidence
    ev = (lead.get("evidence_url") or "") + (lead.get("evidence_snippet") or "")
    ev_ok = bool(ev.strip())
    checks["evidence"] = {"pass": ev_ok, "detail": "present" if ev_ok else "missing evidence_url/snippet"}
    if not ev_ok:
        blockers.append("missing_evidence")

    eligible = len(blockers) == 0
    if eligible:
        pool = "CAMPAIGN_ELIGIBLE"
    elif any(b.startswith("broad_ready:") or b.startswith("hygiene:") or b.startswith("third_party")
             for b in blockers):
        pool = "BLOCKED"
    else:
        pool = "NEEDS_MANUAL_REVIEW"

    return {
        "lead_id": lead_id,
        "store_name": store,
        "email": email,
        "eligible": eligible,
        "pool": pool,
        "checks": checks,
        "blockers": blockers,
        "campaign_eligible_version": "campaign_eligible_v1",
    }


def review_batch(lead_ids: list[int], conn: sqlite3.Connection) -> list[dict]:
    """批量复核。只读，不写库。"""
    conn.row_factory = sqlite3.Row
    out = []
    for lid in lead_ids:
        row = conn.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
        if row is None:
            out.append({"lead_id": lid, "store_name": "?", "eligible": False, "pool": "NOT_FOUND", "blockers": ["lead_not_found"]})
            continue
        out.append(review_campaign_eligible(dict(row), {"conn": conn}))
    return out


def select_candidates_for_plan(conn: sqlite3.Connection, limit: int,
                               states: tuple[str, ...] | None = None) -> list[dict]:
    """正式政策候选选择：Broad Ready → ICP Qualified → Campaign Eligible → Final Send Plan。

    Strict A0 只是优先层，不是唯一发送池。本函数选出 CAMPAIGN_ELIGIBLE 的 lead
    （未渲染，调用方负责 apply_email_to_lead）。只读，不写库、不发送。

    states=None（默认）= 全州允许（P1.7C：州不再作为发送资格硬门禁）；
    传入具体州元组时按州限定（保留旧调用兼容）。
    """
    conn.row_factory = sqlite3.Row
    if states is None:
        rows = conn.execute(
            """SELECT * FROM leads
                WHERE status NOT IN ('sent','bounced','do_not_contact','rejected',
                                     'failed','delivery_issue','bounce_review','contact_form_pool')
                  AND email IS NOT NULL AND email != '' AND email LIKE '%@%.%'
                ORDER BY id"""
        ).fetchall()
    else:
        states_sql = ",".join("?" for _ in states)
        rows = conn.execute(
            f"""SELECT * FROM leads
                WHERE state IN ({states_sql})
                  AND status NOT IN ('sent','bounced','do_not_contact','rejected',
                                     'failed','delivery_issue','bounce_review','contact_form_pool')
                  AND email IS NOT NULL AND email != '' AND email LIKE '%@%.%'
                ORDER BY id"""
            , states).fetchall()
    out: list[dict] = []
    for row in rows:
        lead = dict(row)
        r = review_campaign_eligible(lead, {"conn": conn})
        if r["pool"] == "CAMPAIGN_ELIGIBLE":
            out.append(lead)
            if len(out) >= limit:
                break
    return out


def campaign_eligible_check(conn: sqlite3.Connection) -> callable:
    """返回一个 eligible_check 供 build_final_plan_entries 使用（正式链）。

    判定：review_campaign_eligible 的 pool == CAMPAIGN_ELIGIBLE。
    """
    def _check(lead: dict) -> bool:
        return review_campaign_eligible(lead, {"conn": conn})["pool"] == "CAMPAIGN_ELIGIBLE"
    return _check


if __name__ == "__main__":
    import json
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bd_db import get_db

    ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [774, 783, 779, 777, 781, 780]
    conn = get_db()
    results = review_batch(ids, conn)
    for r in results:
        print(f"[{r['lead_id']}] {r['store_name']} → {r['pool']} | blockers={r['blockers']}")
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    conn.close()
