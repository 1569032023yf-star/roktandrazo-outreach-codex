"""BD Operations Center API — read-only stats for the dashboard.
All functions take a db connection factory and return JSON-safe dicts."""
import importlib.util
import json, os, sqlite3, urllib.request, time
from datetime import datetime, timedelta, timezone

ASIA_SH = timezone(timedelta(hours=8))
TRACKING_BASE = "https://roktandrazo-email-tracker.1569032023yf.workers.dev"

_cache = {}
_cache_ttl = {"tracking": 30, "default": 15}


def _cached(key, ttl_key="default"):
    val = _cache.get(key)
    if val and time.time() - val["t"] < _cache_ttl.get(ttl_key, 15):
        return val["d"]
    return None


def _set_cache(key, data):
    _cache[key] = {"d": data, "t": time.time()}


def _now_shanghai():
    return datetime.now(ASIA_SH)


def _today_str():
    return _now_shanghai().strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════
# D1 tracking fetch
# ═══════════════════════════════════════════════

def _fetch_d1_sql(sql: str):
    """Run SQL against Cloudflare D1 via Worker internal API."""
    try:
        # P7：不再有硬编码默认 key；为空时 Worker 鉴权失败 → 返回 None → 功能 unavailable（fail-closed）
        token = os.environ.get("DASHBOARD_API_KEY", "")
        req = urllib.request.Request(
            f"{TRACKING_BASE}/internal/query",
            data=json.dumps({"sql": sql}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception:
        return None


def get_tracking_stats():
    cached = _cached("tracking_stats", "tracking")
    if cached:
        return cached
    # Read from poller's tracking cache (created by bd_ops_poller via curl transport)
    try:
        cache_path = os.path.join(os.path.dirname(__file__), "output", "bd_ops_poller_tracking_cache.json")
        with open(cache_path, "r") as f:
            data = json.load(f)
        if data.get("available"):
            result = {
                "messages_with_open": data.get("messages_with_open", 0),
                "total_open_signals": data.get("total_open_signals", 0),
                "tracked_sent": data.get("tracked_sent", 0),
                "coverage": round(data.get("messages_with_open", 0) / max(1, data.get("tracked_sent", 1)) * 100, 1),
                "breakdown": data.get("breakdown", {}),
                "available": True,
                "synced_at": data.get("synced_at", ""),
                "source": "poller_cache",
            }
            _set_cache("tracking_stats", result)
            return result
    except Exception:
        pass
    return {"messages_with_open": 0, "total_open_signals": 0, "breakdown": {},
            "coverage": 0, "tracked_sent": 0,
            "available": False, "error": "poller_cache_unavailable"}


# ═══════════════════════════════════════════════
# Today stats
# ═══════════════════════════════════════════════

def get_today_stats(db_path: str):
    t = _today_str()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Planned today
    planned = c.execute("""
        SELECT message_type, COUNT(*) FROM final_send_plan
        WHERE outreach_batch_date = ? AND status = 'planned'
        GROUP BY message_type
    """, (t,)).fetchall()

    # Sent today (by send_log, not sender copies)
    sent = c.execute("""
        SELECT message_type, COUNT(*) FROM send_log
        WHERE outreach_batch_date = ? AND status = 'sent'
          AND message_type IS NOT NULL
          AND message_type NOT IN ('test','internal_report','acceptance_test','sender_copy')
        GROUP BY message_type
    """, (t,)).fetchall()

    # Fallback: sent_at CST date
    sent2 = c.execute("""
        SELECT message_type, COUNT(*) FROM send_log
        WHERE status = 'sent' AND sent_at LIKE ?
          AND message_type NOT IN ('test','internal_report','acceptance_test')
        GROUP BY message_type
    """, (f"{t}%",)).fetchall()

    # Failed / skipped today
    failed = c.execute("""
        SELECT COUNT(*) FROM send_log WHERE status IN ('failed','bounced')
          AND (outreach_batch_date = ? OR sent_at LIKE ?)
          AND message_type NOT IN ('test')
    """, (t, f"{t}%")).fetchone()[0]
    skipped = c.execute("""
        SELECT COUNT(*) FROM final_send_plan 
        WHERE outreach_batch_date = ? AND status = 'skipped'
    """, (t,)).fetchone()[0]

    # Unique orgs sent today
    uniq_orgs = c.execute("""
        SELECT COUNT(DISTINCT COALESCE(NULLIF(l.organization_key,''),'org_'||sl.lead_id))
        FROM send_log sl LEFT JOIN leads l ON sl.lead_id = l.id
        WHERE sl.status = 'sent' AND sl.message_type NOT IN ('test')
          AND (sl.outreach_batch_date = ? OR sl.sent_at LIKE ?)
    """, (t, f"{t}%")).fetchone()[0]

    # Reply / bounce today
    replies = c.execute("SELECT COUNT(*) FROM reply_log WHERE reply_received_at LIKE ?", (f"{t}%",)).fetchone()[0]
    hard_bounces = c.execute("""
        SELECT COUNT(*) FROM bounce_log 
        WHERE bounce_type IN ('hard','policy','permanent') AND bounce_received_at LIKE ?
    """, (f"{t}%",)).fetchone()[0]
    unsub = c.execute("SELECT COUNT(*) FROM leads WHERE unsubscribed_at LIKE ?", (f"{t}%",)).fetchone()[0]

    conn.close()

    def _sum_plans(rows, key="new_outreach"):
        for r in rows:
            if r[0] == key: return r[1]
        return 0

    return {
        "date": t, "timezone": "Asia/Shanghai",
        "planned_new": _sum_plans(planned, "new_outreach"),
        "planned_fw": _sum_plans(planned, "follow_up"),
        "sent_new": _sum_plans(sent or sent2, "new_outreach") or _sum_plans(sent2, "new_outreach"),
        "sent_fw": _sum_plans(sent or sent2, "follow_up") or _sum_plans(sent2, "follow_up"),
        "failed": failed, "skipped": skipped,
        "unique_orgs_sent": uniq_orgs,
        "replies": replies, "hard_bounces": hard_bounces, "unsubscribed": unsub,
    }


# ═══════════════════════════════════════════════
# Inventory
# ═══════════════════════════════════════════════

def get_inventory(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

    type_kw = ['game','toy','book','gift','museum','hobby','education','children',
               'retail','card','puzzle','comic','visitor','souvenir','stationery',
               'craft','general','boutique','department','specialty','independent']
    type_sql = ' OR '.join([f"store_type LIKE '%{t}%'" for t in type_kw])

    def _count(where):
        return c.execute(f"SELECT COUNT(*) FROM leads WHERE {where} AND ({type_sql})").fetchone()[0]

    # Send-preparation candidates
    send_prep = c.execute(f"""SELECT COUNT(*) FROM leads WHERE
        official_website IS NOT NULL AND official_website != ''
        AND (email IS NOT NULL AND email != '' OR contact_form_url IS NOT NULL AND contact_form_url != '')
        AND status NOT IN ('sent','do_not_contact','review_rejected') AND unsubscribed_at IS NULL AND bounced_at IS NULL
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT DISTINCT lead_id FROM send_log WHERE status='sent')
        AND ({type_sql})
    """).fetchone()[0]

    strict_a0 = _count("""status='new' AND confidence_score='A' AND auto_sendable=1
        AND email_verified_on_official_site=1 AND evidence_url IS NOT NULL AND evidence_url != ''
        AND evidence_snippet IS NOT NULL AND evidence_snippet != ''
        AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status='sent')
        AND id NOT IN (SELECT lead_id FROM bounce_log WHERE bounce_type IN ('hard','policy','permanent'))""")

    strict_a0_orgs = c.execute(f"""SELECT COUNT(DISTINCT COALESCE(NULLIF(organization_key,''),'org_'||id))
        FROM leads WHERE status='new' AND confidence_score='A' AND auto_sendable=1
        AND email_verified_on_official_site=1 AND evidence_url IS NOT NULL AND evidence_url != ''
        AND email IS NOT NULL AND email != '' AND ({type_sql})
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status='sent')""").fetchone()[0]

    manual = _count("review_reason_code IS NOT NULL AND review_reason_code != '' AND review_status = 'pending'")
    web_lookup = _count("(review_reason_code = 'WEAK_EVIDENCE' OR notes LIKE '%website_lookup%') AND review_status = 'pending'")
    contact_form = _count("status = 'contact_form_pool' OR review_reason_code = 'CONTACT_FORM_ONLY'")
    low_prio = _count("review_reason_code = 'LOW_PRIORITY' OR (status='manual_review_needed' AND confidence_score='C')")
    prev_sent = _count("id IN (SELECT DISTINCT lead_id FROM send_log WHERE status='sent')")
    suppressed = _count("email IN (SELECT email FROM suppression_list) OR status='do_not_contact' OR unsubscribed_at IS NOT NULL")
    bounce_rec = _count("id IN (SELECT lead_id FROM bounce_log WHERE bounce_type IN ('hard','policy','permanent')) AND id NOT IN (SELECT DISTINCT lead_id FROM send_log WHERE status='sent')")
    staging = c.execute("SELECT COUNT(*) FROM lead_discovery_results").fetchone()[0]

    conn.close()
    return {
        "total_leads": total, "send_prep_candidates": send_prep,
        "strict_a0_locations": strict_a0, "strict_a0_organizations": strict_a0_orgs,
        "org_outreach_opps": strict_a0_orgs,  # same as A0 orgs for now
        "manual_review": manual, "website_lookup": web_lookup,
        "contact_form_only": contact_form, "low_priority": low_prio,
        "previously_sent": prev_sent, "permanently_suppressed": suppressed,
        "bounce_recovery": bounce_rec, "unprocessed_staging": staging,
        "targets": {"critical": 40, "warning": 80, "target": 120},
        "gaps": {"to_40": max(0, 40 - strict_a0_orgs), "to_80": max(0, 80 - strict_a0_orgs),
                 "to_120": max(0, 120 - strict_a0_orgs)},
        "status": "critical" if strict_a0_orgs < 40 else ("warning" if strict_a0_orgs < 80 else "healthy"),
    }


# ═══════════════════════════════════════════════
# Search progress
# ═══════════════════════════════════════════════

def get_search_progress(db_path: str):
    """搜索进度：从 system_config + 城市队列表动态读取，绝不硬编码城市/查询数。

    - active_city ← system_config.active_retail_city
    - active_state ← system_config.active_retail_state 或 active_city_state
    - queries_* ← lead_discovery_query_state（按 retail_city_queue 定位城市）；
      城市无查询记录时回退 system_config 的 search_queries_* JSON 列表。
    - 读取不到 → available=false, status='unknown'（fail-closed，不回退默认城市）。
    """
    result = {
        "available": False, "status": "unknown",
        "active_city": None, "active_state": None, "city_status": None,
        "queries_total": 0, "queries_executed": 0, "queries_remaining": [],
        "current_query": None, "current_source": None,
        "raw_records": 0, "unique_locations": 0, "unique_organizations": 0,
    }
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        def _cfg(key):
            r = c.execute("SELECT value FROM system_config WHERE key=?", (key,)).fetchone()
            return r[0] if r else None

        active_city = _cfg("active_retail_city")
        active_state = _cfg("active_retail_state") or _cfg("active_city_state")
        result["active_city"] = active_city
        result["active_state"] = active_state

        # 城市队列表：优先按 system_config 城市定位；否则取非 QUEUED 的最高优先级城市。
        queue_row = None
        if active_city:
            queue_row = c.execute(
                "SELECT * FROM retail_city_queue WHERE city=? ORDER BY priority LIMIT 1",
                (active_city,)).fetchone()
        if queue_row is None:
            queue_row = c.execute(
                "SELECT * FROM retail_city_queue WHERE status != 'QUEUED' "
                "ORDER BY priority LIMIT 1").fetchone()
        if queue_row is not None:
            result["city_status"] = queue_row["status"]

        # 查询计数：优先 lead_discovery_query_state 按城市定位；无则回退 search_queries_* 配置。
        query_rows = []
        if queue_row is not None:
            query_rows = c.execute(
                "SELECT * FROM lead_discovery_query_state WHERE active_city_id=? ORDER BY id",
                (queue_row["id"],)).fetchall()
        if not query_rows:
            q_list = _cfg("search_queries")
            if not q_list:
                for r in c.execute(
                        "SELECT value FROM system_config WHERE key LIKE 'search_queries_%' "
                        "ORDER BY key LIMIT 1"):
                    q_list = r["value"]
                    break
            if q_list:
                try:
                    q_list = json.loads(q_list)
                except Exception:
                    q_list = None
            if isinstance(q_list, list):
                query_rows = [{"query_family": q, "status": "pending"} for q in q_list]

        if query_rows:
            total = len(query_rows)
            pending_flags = ("pending", "queued")
            executed = sum(1 for r in query_rows if r["status"] not in pending_flags)
            remaining = [r["query_family"] for r in query_rows if r["status"] in pending_flags]
            result.update({
                "queries_total": total,
                "queries_executed": executed,
                "queries_remaining": remaining,
                "current_query": remaining[0] if remaining else query_rows[0]["query_family"],
                "current_source": queue_row["active_source"] if queue_row is not None else None,
                "available": True,
                "status": "in_progress" if remaining else "complete",
            })
    except Exception:
        # fail-closed：任何读取异常都不回退默认城市/查询数
        result["available"] = False
        result["status"] = "unknown"
    finally:
        if conn is not None:
            conn.close()
    return result


# ═══════════════════════════════════════════════
# Final Send Plan
# ═══════════════════════════════════════════════

def get_final_plan(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    by_status = {}
    for r in c.execute("SELECT status, COUNT(*) FROM final_send_plan GROUP BY status"):
        by_status[r[0]] = r[1]

    entries = c.execute("""
        SELECT fsp.*, l.store_name, l.organization_key, l.tracking_message_id
        FROM final_send_plan fsp LEFT JOIN leads l ON fsp.lead_id = l.id
        ORDER BY fsp.planned_sequence
    """).fetchall()

    plan_list = []
    for r in entries:
        d = dict(r)
        plan_list.append({
            "plan_id": d.get("plan_id", ""), "lead_id": d["lead_id"],
            "store": d.get("store_name", ""), "org": d.get("organization_key", ""),
            "recipient": d["recipient_email"][:30] if d.get("recipient_email") else "",
            "type": d["message_type"], "status": d["status"],
            "tracking": d.get("tracking_message_id", ""),
            "batch_date": d.get("outreach_batch_date", ""),
            "sequence": d.get("planned_sequence", 0),
        })
    conn.close()
    return {"by_status": by_status, "total": len(plan_list), "entries": plan_list}


# ═══════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════

def get_delivery_outcome_summary(db_path: str):
    """从 bounce_log 分类统计 + unmatched_dsn + reply_log 生成投递结果摘要。

    SMTP Accepted 只统计 send_log.status='sent'，不因 bounce 减少；
    bounced 邮件视为「已发送但投递失败」，单独在分类中展示。
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()
    try:
        smtp_all = c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent'").fetchone()[0]
        smtp_30d = c.execute(
            "SELECT COUNT(*) FROM send_log WHERE status='sent' AND substr(sent_at,1,10) >= ?",
            ((_now_shanghai() - timedelta(days=30)).strftime("%Y-%m-%d"),)).fetchone()[0]

        raw = {}
        for r in c.execute("SELECT bounce_type, COUNT(*) FROM bounce_log GROUP BY bounce_type"):
            raw[r[0]] = r[1]
        domain_invalid = raw.get("domain_invalid", 0) + raw.get("domain", 0)
        mailbox_invalid = raw.get("mailbox_invalid", 0) + raw.get("mailbox", 0)
        policy_bounce = raw.get("policy_bounce", 0) + raw.get("policy", 0)
        soft_bounce = raw.get("soft_bounce", 0) + raw.get("soft", 0)
        hard_bounce = raw.get("hard", 0)
        other_bounce = sum(v for k, v in raw.items()
                           if k not in ("domain_invalid", "domain", "mailbox_invalid", "mailbox",
                                        "policy_bounce", "policy", "soft_bounce", "soft", "hard"))

        unmatched_dsn = c.execute("SELECT COUNT(*) FROM unmatched_dsn").fetchone()[0]
        if unmatched_dsn == 0:
            row = c.execute("SELECT value FROM system_config WHERE key='last_imap_scan_result'").fetchone()
            if row and row[0]:
                try:
                    scan = json.loads(row[0])
                    unmatched_dsn = int(scan.get("unmatched_dsn") or 0)
                except Exception:
                    pass

        reply_total = c.execute("SELECT COUNT(*) FROM reply_log").fetchone()[0]
        auto_reply = c.execute(
            "SELECT COUNT(*) FROM reply_log WHERE reply_type LIKE '%auto%' "
            "OR reply_type LIKE '%ooo%' OR reply_type LIKE '%autoreply%' "
            "OR reply_type LIKE '%notification%'").fetchone()[0]
        human_reply = reply_total - auto_reply

        classified_total = (domain_invalid + mailbox_invalid + policy_bounce + soft_bounce
                            + hard_bounce + other_bounce + unmatched_dsn
                            + human_reply + auto_reply)
        outcome_unresolved = max(0, smtp_all - classified_total)
    finally:
        conn.close()

    return {
        "smtp_accepted_all": smtp_all,
        "smtp_accepted_30d": smtp_30d,
        "domain_invalid": domain_invalid,
        "mailbox_invalid": mailbox_invalid,
        "policy_bounce": policy_bounce,
        "soft_bounce": soft_bounce,
        "hard_bounce": hard_bounce,
        "other_bounce": other_bounce,
        "unmatched_dsn": unmatched_dsn,
        "human_reply": human_reply,
        "auto_reply": auto_reply,
        "classified_total": classified_total,
        "outcome_unresolved": outcome_unresolved,
    }


def get_data_freshness(db_path: str):
    """读取 system_config 中的扫描/同步时间，返回数据新鲜度状态。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()
    try:
        def cfg(key):
            r = c.execute("SELECT value FROM system_config WHERE key=?", (key,)).fetchone()
            return r[0] if r else None

        last_bounce_scan_at = cfg("last_bounce_scan_at")
        if not last_bounce_scan_at:
            try:
                poller = os.path.join(os.path.dirname(__file__), "output", "bd_ops_poller_status.json")
                with open(poller, "r", encoding="utf-8") as f:
                    p = json.load(f)
                last_bounce_scan_at = (
                    p.get("jobs", {}).get("bounce", {}).get("last_success_at")
                    or p.get("last_heartbeat"))
            except Exception:
                pass
        last_reply_scan_at = (cfg("last_reply_scan_at") or cfg("last_imap_scan_at")
                              or last_bounce_scan_at)
        sync_success_at = cfg("sync_0845_last_success_at")

        level, label = "red", "DATA STALE"
        age_minutes = None
        if last_bounce_scan_at:
            try:
                dt = datetime.fromisoformat(str(last_bounce_scan_at))
            except ValueError:
                dt = None
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ASIA_SH)
                age_minutes = int((_now_shanghai() - dt.astimezone(ASIA_SH)).total_seconds() // 60)
                if age_minutes < 90:
                    level, label = "green", "FRESH"
                elif age_minutes <= 24 * 60:
                    level, label = "yellow", "AGING"
    finally:
        conn.close()

    return {
        "last_bounce_scan_at": last_bounce_scan_at,
        "last_reply_scan_at": last_reply_scan_at,
        "sync_0845_last_success_at": sync_success_at,
        "level": level,
        "badge_label": label,
        "age_minutes": age_minutes,
    }


def get_health(db_path: str):
    result = {"components": {}, "generated_at": _now_shanghai().isoformat()}

    # Review Server
    result["components"]["review_server"] = {"status": "healthy", "port": 8765}

    # Production DB
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        c = conn.cursor()
        qc = c.execute("PRAGMA quick_check").fetchone()[0]
        conn.close()
        result["components"]["database"] = {"status": "healthy" if qc == "ok" else "warning", "quick_check": qc}
    except Exception as e:
        result["components"]["database"] = {"status": "down", "error": str(e)}

    # Tracking Worker
    try:
        r = urllib.request.urlopen(f"{TRACKING_BASE}/healthz", timeout=5)
        h = json.loads(r.read())
        result["components"]["tracking_worker"] = {"status": "healthy" if h.get("status") == "ok" else "warning"}
    except Exception:
        result["components"]["tracking_worker"] = {"status": "down"}

    # SMTP / IMAP config
    result["components"]["smtp"] = {"status": "configured" if os.environ.get("BD_SMTP_USER") or os.path.exists(".env") else "not_configured"}
    result["components"]["imap"] = {"status": "configured" if os.environ.get("BD_IMAP_USER") else "unknown"}

    # Risk gate / scheduler
    try:
        conn2 = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        c2 = conn2.cursor()
        rg = c2.execute("SELECT value FROM system_state WHERE key='risk_gate_status'").fetchone()
        mp = c2.execute("SELECT value FROM system_state WHERE key='manual_pause'").fetchone()
        conn2.close()
        result["risk_gate"] = rg[0] if rg else "unknown"
        result["manual_pause"] = mp[0] if mp else "false"
    except Exception:
        result["risk_gate"] = "unknown"
        result["manual_pause"] = "unknown"

    # Sending window
    h = _now_shanghai().hour
    result["in_send_window"] = 23 <= h or h < 1
    result["current_time_shanghai"] = _now_shanghai().strftime("%Y-%m-%d %H:%M:%S")

    # Delivery Outcome 与数据新鲜度（保持原有字段不动，只新增）
    try:
        result["delivery_outcome"] = get_delivery_outcome_summary(db_path)
    except Exception as e:
        result["delivery_outcome"] = {"error": str(e)}
    try:
        result["data_freshness"] = get_data_freshness(db_path)
    except Exception as e:
        result["data_freshness"] = {"error": str(e)}

    return result


# ═══════════════════════════════════════════════
# Data quality warnings
# ═══════════════════════════════════════════════

def get_data_quality(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()
    warnings = []
    now = _now_shanghai()

    # organization_key empty
    n = c.execute("SELECT COUNT(*) FROM leads WHERE (organization_key IS NULL OR organization_key='') AND status NOT IN ('do_not_contact','review_rejected')").fetchone()[0]
    if n > 10:
        warnings.append({"zh": f"{n} 条线索缺少组织标识", "en": f"{n} leads missing organization_key", "count": n, "link": "/review"})

    # Strict A0 = 0
    a0 = c.execute("SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A' AND auto_sendable=1 AND email_verified_on_official_site=1").fetchone()[0]
    if a0 == 0:
        warnings.append({"zh": "可发送库存为 0", "en": "Zero sendable inventory", "count": 0, "link": "/inventory"})

    # Stale tracking data
    stale = c.execute("SELECT COUNT(*) FROM lead_discovery_results WHERE discovered_at < ?", ((now - timedelta(days=30)).isoformat(),)).fetchone()[0]
    if stale > 0:
        warnings.append({"zh": f"{stale} 条发现数据超过 30 天未处理", "en": f"{stale} discovery results stale >30 days", "count": stale, "link": "/search"})

    # Manual review backlog
    mr = c.execute("SELECT COUNT(*) FROM leads WHERE review_reason_code IS NOT NULL AND review_reason_code != '' AND review_status = 'pending'").fetchone()[0]
    if mr > 50:
        warnings.append({"zh": f"人工审核积压 {mr} 条", "en": f"Manual review backlog: {mr}", "count": mr, "link": "/review"})

    # Expired planned plans
    expired = c.execute("SELECT COUNT(*) FROM final_send_plan WHERE status='planned' AND outreach_batch_date < ?", (_today_str(),)).fetchone()[0]
    if expired > 0:
        warnings.append({"zh": f"{expired} 条过期计划未处理", "en": f"{expired} expired planned entries", "count": expired, "link": "/engagement"})

    # send_log missing message_type
    no_type = c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent' AND (message_type IS NULL OR message_type='') AND lead_id IS NOT NULL").fetchone()[0]
    if no_type > 0:
        warnings.append({"zh": f"{no_type} 条发送记录缺少消息类型", "en": f"{no_type} send_log entries missing message_type", "count": no_type, "link": "/engagement"})

    conn.close()
    return {"warnings": warnings, "generated_at": now.isoformat(), "total": len(warnings)}


# ═══════════════════════════════════════════════
# P0 时区增强 — 发送预览 / 发送结果
# ═══════════════════════════════════════════════

_dashboard_mod = None


def _load_dashboard_module():
    """加载 bd_dashboard_v3.2.py（文件名含点号，须用 importlib）。"""
    global _dashboard_mod
    if _dashboard_mod is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bd_dashboard_v3.2.py")
        spec = importlib.util.spec_from_file_location("bd_dashboard_v3_2", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _dashboard_mod = mod
    return _dashboard_mod


def _ro_conn(db_path: str):
    """只读连接 + Row factory，复用 bd_dashboard_v3.2 的计算函数。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_schedule_preview(db_path: str):
    """发送预览：时区统计 + final_send_plan planned 行的预览明细。"""
    mod = _load_dashboard_module()
    conn = _ro_conn(db_path)
    try:
        stats = mod.compute_timezone_stats(conn)
        entries = mod.compute_schedule_preview(conn)
    finally:
        conn.close()
    return {"stats": stats, "entries": entries}


def get_send_results_tz(db_path: str):
    """发送结果：send_log 最近 30 天 + 时区列 + Delivery Outcome。"""
    mod = _load_dashboard_module()
    conn = _ro_conn(db_path)
    try:
        entries = mod.compute_send_results_tz(conn)
    finally:
        conn.close()
    return {"entries": entries}


def get_schedule_preview_summary(db_path: str):
    """紧凑摘要：时区分布 + UNRESOLVED 数 + 当地 10:00 对应的 China 时间样例。"""
    mod = _load_dashboard_module()
    conn = _ro_conn(db_path)
    try:
        stats = mod.compute_timezone_stats(conn)
        entries = mod.compute_schedule_preview(conn)
    finally:
        conn.close()
    china_samples = [e.get("scheduled_china_time") for e in entries if e.get("scheduled_china_time")]
    return {
        "timezone_distribution": stats.get("distribution", {}),
        "resolved": stats.get("resolved", 0),
        "unresolved": stats.get("unresolved", 0),
        "unresolved_entries": sum(1 for e in entries if e.get("timezone_unresolved")),
        "china_time_sample": china_samples[0] if china_samples else None,
        "sample_count": len(china_samples),
    }


# ═══════════════════════════════════════════════
# Combined summary
# ═══════════════════════════════════════════════

def get_ops_summary(db_path: str):
    def safe(fn, default):
        try: return fn()
        except Exception as e: return default if not isinstance(default, dict) else {"error": str(e), **default}
    return {
        "generated_at": _now_shanghai().isoformat(),
        "timezone": "Asia/Shanghai",
        "today": safe(lambda: get_today_stats(db_path), {"date": _today_str()}),
        "tracking": safe(lambda: get_tracking_stats(), {"available": False}),
        "inventory": safe(lambda: get_inventory(db_path), {}),
        "search": safe(lambda: get_search_progress(db_path), {}),
        "final_plan": safe(lambda: get_final_plan(db_path), {"entries": []}),
        "health": safe(lambda: get_health(db_path), {"components": {}}),
        "data_quality": safe(lambda: get_data_quality(db_path), {"warnings": []}),
        "schedule_preview": safe(lambda: get_schedule_preview(db_path), {"entries": []}),
        "send_results_tz": safe(lambda: get_send_results_tz(db_path), {"entries": []}),
    }
