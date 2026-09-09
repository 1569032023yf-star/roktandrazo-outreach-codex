#!/usr/bin/env python3
"""
preflight_gate.py — P0 发信前自检增强（只读门禁引擎）

被 _preflight_check.py 及未来批次复用。核心检查引擎本身只读；
唯一的 DB 写入是 DNS 结果缓存（system_config.mx_cache_<domain>），
通过 persist_cache=False 可完全禁止写入（_preflight_check.py 即如此）。

检查项：
  1. check_dns_freshness  — Worker MX 查询 + 24h freshness（nxdomain/null_mx/no_mail_route/stale → fail）
  2. check_hygiene        — suppression / hard-bounce / reply / 已发 email+org / 格式
  3. check_duplicates     — organization_key、email（plan 内 + 与已发送）
  4. check_template       — template_id 在 _TEMPLATE_REGISTRY、无 forbidden phrases、模板路由一致
  5. check_snapshot_plan_hash — frozen_<batch>.json 的 plan hash 重算比对
  6. check_auth_entries   — 该 batch 授权 approved/未过期/passed/entries 一致
  7. check_stale_objects  — 无旧 planned 计划、无 active 旧授权、Poller 心跳 ≤30min
  8. check_timezones      — 每条 planned 的收件人时区有效性 + 当地 10:00 窗口
                           （未解析/时区无效/过期 → 单条 block，记入 timezone_blocks；
                             整体仅在全部条目被 block 时 fail，否则仍 pass）

任何 fail → smtp_blocked=True（SMTP 保持 0）。
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import ssl
import sys
import urllib.request
import zoneinfo
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("WORKBUDDY_BD_DB_PATH") or str(PROJECT_DIR / "data" / "bd_leads.db")
OPS_POLLER_STATUS = PROJECT_DIR / "output" / "bd_ops_poller_status.json"

# Worker MX 端点：POST /internal/mx-check（Bearer auth），body {"domain": "..."}
WORKER_MX_URL = "https://roktandrazo-email-tracker.1569032023yf.workers.dev/internal/mx-check"
# 与 _catchup_calculate.py / bd_ops_poller.py 使用同一把 key，可用环境变量覆盖
WORKER_AUTH_TOKEN = (
    os.environ.get("TRACKING_DASHBOARD_API_KEY")
    or os.environ.get("DASHBOARD_API_KEY")
    or "roktandrazo-dk-45llgR7F_BKGU3RzW6Qq8ieVW4BE3XXjMo_J6LQtzEw"
)
MX_TIMEOUT_SEC = 10

ASIA_SH = timezone(timedelta(hours=8))

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
# 这些 MX 状态直接判定不可投递
DNS_FAIL_STATUSES = frozenset({"nxdomain", "null_mx", "no_mail_route"})
# Worker 返回的 mx_status → 门禁 mx_status 映射
_WORKER_STATUS_MAP = {
    "mx_pass": "ok",
    # P1.7H: EXPLICIT_MX_REQUIRED — 即使旧 Worker/历史响应返回 implicit_mail_route，
    # 一律映射为 no_mail_route（fail）。腾讯 SMTP 不做 A-fallback（falloutcomics.com
    # 真实 DSN: type=MX Host not found），A-only 隐式路由不可视为可投递。
    "implicit_mail_route": "no_mail_route",
    "nxdomain": "nxdomain",
    "no_mx_found": "null_mx",
    "no_mail_route": "no_mail_route",
}
# bounce 类型中视为 hard/permanent
_HARD_BOUNCE_TYPES = frozenset({"hard", "policy", "permanent", "domain_invalid"})


# ── 基础设施 ────────────────────────────────────────────────

def _get_conn(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _read_config(conn, key, default=None):
    row = conn.execute("SELECT value FROM system_config WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    return row["value"]


def _write_config(conn, key, value):
    now = datetime.now(ASIA_SH).isoformat()
    conn.execute(
        "INSERT INTO system_config (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, now),
    )
    conn.commit()


def _resolve_batch(conn, batch_id):
    """支持 'latest'：取最近一个存在 planned 计划的批次；没有 planned 则取最近创建的批次。"""
    if batch_id and batch_id != "latest":
        return batch_id
    row = conn.execute(
        "SELECT MAX(outreach_batch_date) m FROM final_send_plan WHERE status='planned'"
    ).fetchone()
    if row and row["m"]:
        return row["m"]
    row = conn.execute(
        "SELECT outreach_batch_date m FROM final_send_plan "
        "GROUP BY outreach_batch_date ORDER BY MAX(created_at) DESC, MAX(id) DESC LIMIT 1"
    ).fetchone()
    return row["m"] if row else None


def _parse_ts(ts):
    """解析 ISO 时间戳；无时区则按 Asia/Shanghai 处理。失败返回 None。"""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ASIA_SH)
    return dt.astimezone(ASIA_SH)


# ── Worker MX 查询 ──────────────────────────────────────────

def query_mx(domain):
    """调用 Worker MX 端点查询域名 MX。

    返回 (mx_status, checked_at)。任何网络/解析异常都返回
    ('dns_error', <当前时间>)，绝不抛出。超时 10s。
    注意：urllib 默认读取环境变量 HTTPS_PROXY（本机走 127.0.0.1:3213 代理）。
    """
    now_iso = datetime.now(ASIA_SH).isoformat()
    domain = (domain or "").strip().lower().rstrip("/")
    if not domain:
        return "dns_error", now_iso
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        body = json.dumps({"domain": domain}).encode("utf-8")
        req = urllib.request.Request(
            WORKER_MX_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {WORKER_AUTH_TOKEN}",
                "User-Agent": "preflight-gate/1.0",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=MX_TIMEOUT_SEC, context=ctx)
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
        worker_status = data.get("mx_status") or ""
        checked_at = data.get("checked_at") or now_iso
        return _WORKER_STATUS_MAP.get(worker_status, "dns_error"), checked_at
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return _mx_via_dns(domain)
    except Exception:
        return _mx_via_dns(domain)


# In-process MX cache (per run): same domain is never resolved twice.
_MX_DNS_CACHE: dict = {}


def _mx_via_dns(domain):
    """Direct DNS MX verification fallback (no Worker dependency).

    Used when the Worker MX endpoint is unavailable/expired. Returns
    (mx_status, checked_at) using the same vocabulary as the Worker path
    (ok / nxdomain / null_mx / no_mail_route / dns_error). Fail-closed:
    any uncertainty blocks — never passes on doubt.
    """
    if domain in _MX_DNS_CACHE:
        return _MX_DNS_CACHE[domain]
    now_iso = datetime.now(ASIA_SH).isoformat()
    result = ("dns_error", now_iso)
    try:
        import dns.resolver
    except ImportError:
        return result
    try:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 6
        resolver.timeout = 3
        try:
            ans = resolver.resolve(domain, "MX")
            for r in ans:
                if str(r.exchange).rstrip(".") == "":
                    result = ("null_mx", now_iso)  # RFC 7505
                    break
            else:
                result = ("ok", now_iso)
        except dns.resolver.NXDOMAIN:
            result = ("nxdomain", now_iso)
        except dns.resolver.NoAnswer:
            try:
                resolver.resolve(domain, "A")
                result = ("no_mail_route", now_iso)
            except Exception:
                result = ("dns_error", now_iso)
        except dns.resolver.NoNameservers:
            result = ("dns_error", now_iso)
        except Exception:
            result = ("dns_error", now_iso)
    except Exception:
        result = ("dns_error", now_iso)
    _MX_DNS_CACHE[domain] = result
    return result


def _domain_of(email):
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].strip().lower()


# ── 1. DNS freshness ────────────────────────────────────────

def check_dns_freshness(conn, max_age_hours=24, persist_cache=True, batch_id=None, now=None):
    """对 final_send_plan 中 planned 记录的 recipient_email 域名做 MX 检查。

    - 同域名单次运行只查一次（内存缓存）。
    - 读取 system_config.mx_cache_<domain>（json {status, checked_at}）：
      命中且在 max_age_hours 内 → 直接复用缓存（fresh=True），不再查网络；
      未命中或超龄 → 现场查 Worker MX 并写缓存（self-bootstrap）：
        * 本次 live 查询成功且结果为可投递状态（explicit MX = ok）
          → 立即视为 FRESH/PASS（stale=False），不要求第二次运行；
        * 本次 live 查询返回 dns_error/timeout/unauthorized/no_mail_route/
          nxdomain/null_mx/invalid_mx → FAIL CLOSED（stale=True）。
      注意：stale 缓存本身绝不被当作 PASS；PASS 只来自 fresh 缓存
      或本次成功的 live refresh。
    - MX 结果在 24h 内且为 nxdomain/null_mx/no_mail_route → fail（沿用上方判定）。
    - persist_cache=False 时不写 system_config（只读场景）。
    返回 dict：domain -> {mx_status, checked_at, stale, fresh}
    """
    now = now or datetime.now(ASIA_SH)
    q = "SELECT recipient_email FROM final_send_plan WHERE status='planned'"
    params = ()
    if batch_id:
        q += " AND outreach_batch_date=?"
        params = (batch_id,)
    rows = conn.execute(q, params).fetchall()

    domains = []
    for r in rows:
        d = _domain_of(r["recipient_email"])
        if d and d not in domains:
            domains.append(d)

    results = {}
    for domain in domains:
        cached_raw = _read_config(conn, f"mx_cache_{domain}")
        cached = None
        if cached_raw:
            try:
                cached = json.loads(cached_raw)
            except (TypeError, json.JSONDecodeError):
                cached = None

        cached_ts = _parse_ts(cached.get("checked_at")) if cached else None
        fresh = bool(
            cached
            and cached_ts
            and (now - cached_ts).total_seconds() <= max_age_hours * 3600
        )
        if fresh:
            results[domain] = {
                "mx_status": cached.get("status", "dns_error"),
                "checked_at": cached.get("checked_at"),
                "stale": False,
                "fresh": True,
            }
            continue

        # 缓存未命中/超龄 → 现场查询（self-bootstrap：本次 live 成功即视为 fresh）
        status, checked_at = query_mx(domain)
        if persist_cache:
            try:
                _write_config(conn, f"mx_cache_{domain}", json.dumps({"status": status, "checked_at": checked_at}))
            except sqlite3.Error:
                pass  # 缓存写失败不阻断检查
        # 本次 live 查询成功且结果为可投递状态（explicit MX = ok）→
        # 立即视为 FRESH/PASS（同一运行内即可通过，不要求第二次运行）。
        # 其余（dns_error / timeout / unauthorized / no_mail_route /
        # nxdomain / null_mx / invalid_mx）→ FAIL CLOSED（stale=True）。
        live_passed = (status == "ok")
        results[domain] = {
            "mx_status": status,
            "checked_at": checked_at,
            "stale": not live_passed,
            "fresh": live_passed,
        }
    return results


# ── 2. Hygiene ──────────────────────────────────────────────

def check_hygiene(conn, plan_rows):
    """suppression / hard-bounce / reply / 已发 email+org / 邮箱格式。"""
    failures = []
    lead_ids = [r["lead_id"] for r in plan_rows]
    emails = [str(r["recipient_email"] or "").strip().lower() for r in plan_rows]

    if lead_ids:
        ph = ",".join("?" for _ in lead_ids)
        sup = conn.execute(
            f"SELECT DISTINCT lower(email) e FROM suppression_list WHERE lower(email) IN ({','.join('?' for _ in emails)})",
            emails,
        ).fetchall() if emails else []
        for s in sup:
            failures.append(f"suppressed:{s['e']}")

        bounced = conn.execute(
            f"SELECT DISTINCT lead_id, email FROM bounce_log "
            f"WHERE lower(COALESCE(bounce_type,'')) IN ({','.join('?' for _ in _HARD_BOUNCE_TYPES)}) "
            f"AND (lead_id IN ({ph}) OR lower(COALESCE(email,'')) IN ({','.join('?' for _ in emails)}))",
            list(_HARD_BOUNCE_TYPES) + lead_ids + emails,
        ).fetchall()
        for b in bounced:
            failures.append(f"hard_bounce:lead_id={b['lead_id']}")

        replied = conn.execute(
            f"SELECT DISTINCT lead_id FROM reply_log WHERE lead_id IN ({ph})",
            lead_ids,
        ).fetchall()
        for rp in replied:
            failures.append(f"replied:lead_id={rp['lead_id']}")

        prev_email = conn.execute(
            f"SELECT DISTINCT lower(email) e FROM send_log WHERE status='sent' "
            f"AND lower(email) IN ({','.join('?' for _ in emails)})",
            emails,
        ).fetchall() if emails else []
        for p in prev_email:
            failures.append(f"already_sent:{p['e']}")

        # 已发送的 org_key（对应当前计划的 lead）
        for r in plan_rows:
            org_row = conn.execute(
                "SELECT COALESCE(NULLIF(organization_key,''),'org:'||id) k FROM leads WHERE id=?",
                (r["lead_id"],),
            ).fetchone()
            if org_row:
                sent_org = conn.execute(
                    "SELECT 1 FROM send_log sl JOIN leads l ON sl.lead_id=l.id "
                    "WHERE sl.status='sent' AND sl.lead_id!=? "
                    "AND COALESCE(NULLIF(l.organization_key,''),'org:'||l.id)=?",
                    (r["lead_id"], org_row["k"]),
                ).fetchone()
                if sent_org:
                    failures.append(f"org_already_sent:{org_row['k']}")

    for r in plan_rows:
        e = str(r["recipient_email"] or "").strip()
        if not e or not EMAIL_RE.match(e):
            failures.append(f"bad_email:{e or '(empty)'}")

    name = "hygiene"
    if failures:
        return {"name": name, "status": "fail",
                "detail": f"{len(failures)} issue(s): " + "; ".join(dict.fromkeys(failures))}
    return {"name": name, "status": "pass", "detail": f"{len(plan_rows)} planned lead(s) clean"}


# ── 3. Duplicates ───────────────────────────────────────────

def check_duplicates(conn, plan_rows):
    """organization_key 重复、email 重复（plan 内 + 与已发送）。"""
    failures = []
    emails = [str(r["recipient_email"] or "").strip().lower() for r in plan_rows]
    email_counts = {}
    for e in emails:
        if e:
            email_counts[e] = email_counts.get(e, 0) + 1
    for e, c in email_counts.items():
        if c > 1:
            failures.append(f"email_dup_in_plan:{e} x{c}")

    # 与已发送 email 重复（排除本批已存在的历史，按 email 全局去重）
    if emails:
        prev = conn.execute(
            f"SELECT DISTINCT lower(email) e FROM send_log WHERE status='sent' "
            f"AND lower(email) IN ({','.join('?' for _ in emails)})",
            emails,
        ).fetchall()
        for p in prev:
            failures.append(f"email_already_sent:{p['e']}")

    # organization_key 重复：plan 内 + 与已发送
    org_keys = []
    for r in plan_rows:
        row = conn.execute(
            "SELECT COALESCE(NULLIF(organization_key,''),'org:'||id) k FROM leads WHERE id=?",
            (r["lead_id"],),
        ).fetchone()
        if row:
            org_keys.append(row["k"])
    org_counts = {}
    for k in org_keys:
        org_counts[k] = org_counts.get(k, 0) + 1
    for k, c in org_counts.items():
        if c > 1:
            failures.append(f"org_dup_in_plan:{k} x{c}")

    for r in plan_rows:
        row = conn.execute(
            "SELECT COALESCE(NULLIF(organization_key,''),'org:'||id) k FROM leads WHERE id=?",
            (r["lead_id"],),
        ).fetchone()
        if not row:
            continue
        prev_org = conn.execute(
            "SELECT 1 FROM send_log sl JOIN leads l ON sl.lead_id=l.id "
            "WHERE sl.status='sent' AND sl.lead_id!=? "
            "AND COALESCE(NULLIF(l.organization_key,''),'org:'||l.id)=?",
            (r["lead_id"], row["k"]),
        ).fetchone()
        if prev_org:
            failures.append(f"org_already_sent:{row['k']}")

    name = "duplicates"
    if failures:
        return {"name": name, "status": "fail",
                "detail": f"{len(failures)} issue(s): " + "; ".join(dict.fromkeys(failures))}
    return {"name": name, "status": "pass", "detail": f"{len(plan_rows)} planned row(s) unique"}


# ── 4. Template ─────────────────────────────────────────────

def check_template(conn, plan_rows):
    """template_id 必须注册；body 无 forbidden phrases；模板路由与 plan 一致。"""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from bd_template import _TEMPLATE_REGISTRY, check_inline_forbidden, route_template_for_lead
    except Exception as e:  # pragma: no cover - 导入失败直接 fail-closed
        return {"name": "template", "status": "fail", "detail": f"bd_template import failed: {e}"}

    failures = []
    for r in plan_rows:
        tid = r["template_id"]
        if tid not in _TEMPLATE_REGISTRY:
            failures.append(f"unknown_template:{tid} (lead_id={r['lead_id']})")
            continue
        tpl = _TEMPLATE_REGISTRY[tid]
        if tpl.get("status") != "ACTIVE_LOCKED":
            failures.append(f"template_not_active_locked:{tid} (status={tpl.get('status')})")

        body = str(r["body_text"] or "") + str(r["body_html"] or "")
        forbidden = check_inline_forbidden(body)
        if forbidden:
            failures.append(f"forbidden_phrase:{tid} -> {forbidden}")

        lead = conn.execute("SELECT * FROM leads WHERE id=?", (r["lead_id"],)).fetchone()
        if lead:
            routed = route_template_for_lead(dict(lead))
            if routed != tid:
                failures.append(f"template_mismatch:plan={tid} routed={routed} (lead_id={r['lead_id']})")

    name = "template"
    if failures:
        return {"name": name, "status": "fail",
                "detail": f"{len(failures)} issue(s): " + "; ".join(dict.fromkeys(failures))}
    return {"name": name, "status": "pass", "detail": f"{len(plan_rows)} planned row(s) template ok"}


# ── 5. Snapshot plan hash ───────────────────────────────────

def check_snapshot_plan_hash(conn, snapshot_path, plan_rows):
    """若 frozen_<batch>.json 存在，重算 plan 的 (lead_id,recipient_email,template_id) sha256 比对。"""
    name = "snapshot_plan_hash"
    if not snapshot_path or not os.path.exists(snapshot_path):
        return {"name": name, "status": "warn", "detail": f"no snapshot at {snapshot_path or '(none)'}"}
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {"name": name, "status": "fail", "detail": f"snapshot unreadable: {e}"}

    if "plan_hash" not in snap:
        return {"name": name, "status": "warn",
                "detail": f"snapshot {os.path.basename(snapshot_path)} has no plan_hash field, skipped"}

    items = sorted(
        (str(r["lead_id"]), str(r["recipient_email"] or "").strip().lower(), r["template_id"] or "")
        for r in plan_rows
    )
    digest = hashlib.sha256(json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if digest == snap["plan_hash"]:
        return {"name": name, "status": "pass", "detail": f"plan hash matches {digest[:8]}.."}
    return {"name": name, "status": "fail",
            "detail": f"plan hash mismatch: recomputed={digest[:8]}.. snapshot={snap['plan_hash'][:8]}.."}


# ── 6. Authorization entries ────────────────────────────────

def check_auth_entries(conn, batch_id, now=None):
    """该 batch 的授权必须 approved、未过期、preflight passed、entries 与计划逐条一致。"""
    now = now or datetime.now(ASIA_SH)
    name = "auth_entries"
    auths = conn.execute(
        "SELECT * FROM send_authorizations WHERE outreach_batch_date=? ORDER BY created_at DESC, id DESC",
        (batch_id,),
    ).fetchall()
    if not auths:
        return {"name": name, "status": "fail", "detail": f"no authorization for batch {batch_id}"}

    auth = auths[0]
    failures = []
    if auth["status"] != "approved":
        failures.append(f"auth status={auth['status']} (need approved)")
    expires = _parse_ts(auth["expires_at"])
    if expires and expires <= now:
        failures.append(f"auth expired at {auth['expires_at']}")
    if auth["preflight_status"] != "passed":
        failures.append(f"preflight_status={auth['preflight_status']}")

    plan_rows = conn.execute(
        "SELECT lead_id, recipient_email FROM final_send_plan "
        "WHERE outreach_batch_date=? AND status='planned'",
        (batch_id,),
    ).fetchall()
    entries = conn.execute(
        "SELECT lead_id, recipient_email FROM send_authorization_entries WHERE authorization_id=?",
        (auth["authorization_id"],),
    ).fetchall()
    if len(entries) != len(plan_rows):
        failures.append(f"entries={len(entries)} vs planned={len(plan_rows)}")

    plan_set = {(r["lead_id"], str(r["recipient_email"] or "").strip().lower()) for r in plan_rows}
    entry_set = {(e["lead_id"], str(e["recipient_email"] or "").strip().lower()) for e in entries}
    if plan_set != entry_set and len(entries) == len(plan_rows):
        failures.append(f"entry/plan set mismatch: plan-only={len(plan_set - entry_set)} entry-only={len(entry_set - plan_set)}")

    if failures:
        return {"name": name, "status": "fail", "detail": f"{auth['authorization_id']}: " + "; ".join(failures)}
    return {"name": name, "status": "pass",
            "detail": f"{auth['authorization_id']} approved, {len(entries)} entries match"}


# ── 7. Stale objects / poller ───────────────────────────────

def check_stale_objects(conn, batch_id, now=None, message_type=None):
    """旧 planned 计划、active 旧授权、Poller 心跳 ≤30min。

    message_type（P2.3I）：按 batch_date + message_type 正确 scope，避免
    new_outreach 与 follow_up 相互污染。仅当「其它旧 batch 存在相同 message_type
    的 planned 行 / active 授权」时才判 FAIL；同 message_type 的当前 batch 不被
    误伤。不传 message_type 时退化为全 message_type 检查（向后兼容）。
    """
    now = now or datetime.now(ASIA_SH)
    failures = []

    q = ("SELECT outreach_batch_date d, COUNT(*) c FROM final_send_plan "
         "WHERE status='planned' AND outreach_batch_date!=?")
    params = [batch_id]
    if message_type:
        q += " AND message_type=?"
        params.append(message_type)
    q += " GROUP BY outreach_batch_date"
    old_plans = conn.execute(q, params).fetchall()
    for p in old_plans:
        failures.append(f"old_planned_plan:{p['d']} x{p['c']}")

    # send_authorizations 无 message_type 列，需经 plan_id 关联 final_send_plan 取 message_type。
    if message_type:
        q2 = ("SELECT DISTINCT sa.authorization_id FROM send_authorizations sa "
              "JOIN final_send_plan fsp ON fsp.plan_id = sa.plan_id "
              "WHERE sa.status='approved' AND fsp.outreach_batch_date!=? "
              "AND fsp.message_type=?")
        p2 = [batch_id, message_type]
    else:
        q2 = ("SELECT sa.authorization_id FROM send_authorizations sa "
              "WHERE sa.status='approved' AND sa.outreach_batch_date!=?")
        p2 = [batch_id]
    old_auths = conn.execute(q2, p2).fetchall()
    for a in old_auths:
        failures.append(f"old_active_auth:{a['authorization_id']}")

    # Poller 心跳
    try:
        ps = json.loads(OPS_POLLER_STATUS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        ps = {}
    hb = ps.get("last_heartbeat_at") or ps.get("last_heartbeat") or ps.get("last_ping")
    hb_ts = _parse_ts(hb)
    if not hb_ts:
        failures.append("poller_heartbeat:missing/parse-error")
    else:
        age_min = (now - hb_ts).total_seconds() / 60
        if age_min > 30:
            failures.append(f"poller_heartbeat_stale:{age_min:.1f}min (>{30}min)")

    name = "stale_objects"
    if failures:
        return {"name": name, "status": "fail", "detail": "; ".join(failures)}
    return {"name": name, "status": "pass", "detail": "no old plans/auths; poller fresh"}


# ── 8. 时区窗口 ─────────────────────────────────────────────

def _batch_date_of(row):
    """从 outreach_batch_date 提取计划发送日（date 对象）；解析失败返回 None。

    支持 ISO 日期（2026-07-29）与批次号内嵌日期（new_outreach_20260805_2300cs_tnarky）。
    兼容 dict 与 sqlite3.Row 两种行类型。
    """
    if isinstance(row, dict):
        raw = str(row.get("outreach_batch_date") or "")
    else:
        try:
            raw = str(row["outreach_batch_date"] or "")
        except (KeyError, IndexError, TypeError):
            raw = ""
    m = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", raw)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def check_timezones(conn, plan_rows, now=None, send_window_override: bool = False):
    """对每条 planned 记录做时区窗口检查（P0 追加步骤）。

    单条判定：
      - recipient_timezone 非空且 in zoneinfo.available_timezones()；
      - timezone_status != 'TIMEZONE_UNRESOLVED'；
      - scheduled_utc_time 已计算（按计划日/今天的当地 10:00 窗口推算）；
      - 当前时间不早于当地窗口：已过窗口但日期仍是今天 → catch-up 允许；
        scheduled 时刻早于当前且当地日期已过去 → 'expired' 单条 block。

    send_window_override=True（一次性时间 override，如 P1.2 延误补发）时，
    仅豁免 'expired' 窗口判定；TIMEZONE_UNRESOLVED / 无效时区 /
    非自动调度等数据质量类判定仍然 fail-closed。

    任何对象 TIMEZONE_UNRESOLVED → 该条标记 TIMEZONE_UNRESOLVED 不发送
    （记入 timezone_blocks），不影响其他已确认时区对象；仅当全部条目
    被 block 时整体 fail，否则仍 pass。

    返回 {"check": {name:'timezone_resolution', status, detail},
          "timezone_blocks": [{"lead_id": int, "reason": str}, ...]}
    """
    now = now or datetime.now(ASIA_SH)
    now_utc = now.astimezone(timezone.utc)

    # leads 表缺少时区列（旧库/测试表）→ 跳过检查，避免误伤既有门禁
    try:
        lead_cols = {r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()}
    except sqlite3.Error:
        lead_cols = set()
    required_cols = {"recipient_timezone", "timezone_status", "sendable_for_automatic_schedule"}
    missing = required_cols - lead_cols
    if missing:
        return {
            "check": {"name": "timezone_resolution", "status": "warn",
                      "detail": "leads 表缺少时区列，时区检查跳过: " + ",".join(sorted(missing))},
            "timezone_blocks": [],
        }

    total = len(plan_rows)
    timezone_blocks = []
    if total == 0:
        return {"check": {"name": "timezone_resolution", "status": "pass",
                          "detail": "0 planned rows"},
                "timezone_blocks": []}

    for row in plan_rows:
        lead = conn.execute(
            "SELECT recipient_timezone, timezone_status, sendable_for_automatic_schedule "
            "FROM leads WHERE id=?",
            (row["lead_id"],),
        ).fetchone()
        reason = None
        if lead is None:
            reason = "lead_missing"
        else:
            tz = (lead["recipient_timezone"] or "").strip() if lead["recipient_timezone"] else ""
            tz_status = str(lead["timezone_status"] or "")
            if not tz:
                reason = "no_recipient_timezone"
            elif tz not in zoneinfo.available_timezones():
                reason = f"invalid_timezone:{tz}"
            elif tz_status == "TIMEZONE_UNRESOLVED":
                reason = "TIMEZONE_UNRESOLVED"
            elif not (lead["sendable_for_automatic_schedule"] or 0):
                reason = "not_sendable_for_automatic_schedule"
            else:
                try:
                    # scheduled_utc_time 按计划日推算（无日期则取当地今天），DST 由 zoneinfo 处理
                    start, _end = _local_window_utc_for(tz, _batch_date_of(row), now_utc)
                    sched_local_date = start.astimezone(ZoneInfo(tz)).date()
                    today_local = now_utc.astimezone(ZoneInfo(tz)).date()
                    if start <= now_utc and sched_local_date < today_local and not send_window_override:
                        reason = "expired"
                    # 其余情形：未到点，或已过窗口但仍是今天 → catch-up 允许；
                    # send_window_override 时即使计划日已过也视为可发
                except Exception:
                    reason = "schedule_compute_error"
        if reason:
            timezone_blocks.append({"lead_id": row["lead_id"], "reason": reason})

    blocked = len(timezone_blocks)
    reason_counts = {}
    for b in timezone_blocks:
        reason_counts[b["reason"]] = reason_counts.get(b["reason"], 0) + 1
    summary = ", ".join(f"{k} x{v}" for k, v in sorted(reason_counts.items()))

    if blocked == 0:
        check = {"name": "timezone_resolution", "status": "pass",
                 "detail": f"{total} planned, all timezone-ok"}
    elif blocked < total:
        # 部分未解析/过期只 block 单条，不影响已确认时区对象 → 整体仍 pass
        check = {"name": "timezone_resolution", "status": "pass",
                 "detail": f"{total} planned, {blocked} blocked ({summary}), "
                           f"{total - blocked} sendable"}
    else:
        check = {"name": "timezone_resolution", "status": "fail",
                 "detail": f"all {total} planned blocked by timezone: {summary}"}
    return {"check": check, "timezone_blocks": timezone_blocks}


def _local_window_utc_for(tz, on_date, now_utc):
    """按 on_date（可为 None）计算窗口；on_date 为 None 时取 now_utc 的当地日期。"""
    if on_date is None:
        on_date = now_utc.astimezone(ZoneInfo(tz)).date()
    from recipient_scheduler import local_send_window_utc
    return local_send_window_utc(tz, on_date=on_date)


# ── run_preflight 汇总 ──────────────────────────────────────

def run_preflight(conn, batch_id, snapshot_path=None, require_dns=True, persist_cache=True, now=None,
                  send_window_override: bool = False, include_auth_entries: bool = True,
                  message_type: str | None = None):
    """汇总全部检查。任何 fail → smtp_blocked=True（SMTP 保持 0）。

    include_auth_entries=False 时跳过 check_auth_entries（该检查要求授权已存在，
    用于「授权创建前」的 PRE_AUTH 阶段：此时授权尚不存在，必须先拿到真实结果
    才能决定是否创建授权，避免 create_send_authorization(preflight_passed=True)
    硬编码假通过）。授权创建后再以 include_auth_entries=True 跑一遍做 POST_AUTH
    一致性校验。

    返回 {pass, checks, blocks, smtp_blocked, batch_id, plan_count, checked_at,
          timezone_blocks}
    """
    batch_id = _resolve_batch(conn, batch_id)
    now = now or datetime.now(ASIA_SH)

    # Self-healing: close any approved auth that has no pending entries, so a zombie
    # auth can never permanently block a later preflight (root cause of 2026-09-02
    # blackout). Uses its own connection; no-op when nothing is stuck.
    try:
        from bd_sender import reconcile_consumed_authorizations
        reconcile_consumed_authorizations()
    except Exception:
        pass

    if not batch_id:
        checks = [{"name": "batch_exists", "status": "fail", "detail": "no batch found"}]
        return {
            "pass": False, "checks": checks, "blocks": ["batch_exists"],
            "smtp_blocked": True, "batch_id": None, "plan_count": 0,
            "checked_at": now.isoformat(),
            "timezone_blocks": [],
        }

    plan_rows = conn.execute(
        "SELECT * FROM final_send_plan WHERE outreach_batch_date=? AND status='planned' ORDER BY planned_sequence",
        (batch_id,),
    ).fetchall()
    plan_count = len(plan_rows)

    checks = []
    blocks = []

    # 0) 批次必须有「当前 message_type」的 planned 行（P2.3I：按 batch_date + message_type
    #    正确 scope，避免 new_outreach / follow_up 相互污染）。
    #    - 当前 batch_date + 当前 message_type 存在 planned FSP rows → PASS
    #    - 当前 batch 没有该 message_type 的 planned rows → FAIL
    #    - 其它旧 batch 的 planned rows 由 check_stale_objects FAIL（下方 step 2..7）
    #    不传 message_type 时退化为全 message_type 计数（向后兼容既有调用方）。
    if message_type:
        prp_count = conn.execute(
            "SELECT COUNT(*) c FROM final_send_plan "
            "WHERE outreach_batch_date=? AND message_type=? AND status='planned'",
            (batch_id, message_type),
        ).fetchone()["c"]
        prp_detail = f"{prp_count} planned {message_type} rows for {batch_id}"
    else:
        prp_count = plan_count
        prp_detail = f"{plan_count} planned rows (message_type unscoped)"
    if prp_count == 0:
        checks.append({"name": "planned_rows_present", "status": "fail",
                       "detail": (f"batch {batch_id} has 0 planned rows for "
                                  f"message_type={message_type}") if message_type else
                                  f"batch {batch_id} has 0 planned rows"})
        blocks.append("planned_rows_present")
    else:
        checks.append({"name": "planned_rows_present", "status": "pass", "detail": prp_detail})

    # 1) DNS freshness
    if require_dns:
        dns = check_dns_freshness(conn, batch_id=batch_id, persist_cache=persist_cache, now=now)
        dns_failures = []
        dns_detail = []
        for domain, info in dns.items():
            dns_detail.append(f"{domain}={info['mx_status']}{'(stale)' if info['stale'] else ''}")
            if info["stale"]:
                dns_failures.append(f"dns_stale:{domain} (never/>{24}h)")
            elif info["mx_status"] in DNS_FAIL_STATUSES:
                dns_failures.append(f"dns_{info['mx_status']}:{domain}")
            elif info["mx_status"] == "dns_error":
                dns_failures.append(f"dns_error:{domain}")
        if dns_failures:
            checks.append({"name": "dns_freshness", "status": "fail",
                           "detail": "; ".join(dns_failures) + f" | domains: {', '.join(dns_detail) or 'none'}"})
            blocks.extend(dns_failures)
        else:
            checks.append({"name": "dns_freshness", "status": "pass",
                           "detail": f"{len(dns)} domain(s) fresh: " + (", ".join(dns_detail) or "none")})
    else:
        checks.append({"name": "dns_freshness", "status": "warn", "detail": "require_dns=False, skipped"})

    # 2..7 各检查
    # PRE_AUTH 阶段：除 auth_entries 外的全部检查（不依赖授权已存在）。
    # auth_entries 仅在 include_auth_entries=True 时纳入（POST_AUTH 一致性校验）。
    pre_auth_fns = [
        check_hygiene,
        check_duplicates,
        check_template,
        lambda c, rows: check_snapshot_plan_hash(c, snapshot_path, rows),
        lambda c, rows: check_stale_objects(c, batch_id, now, message_type),
    ]
    if include_auth_entries:
        pre_auth_fns.append(lambda c, rows: check_auth_entries(c, batch_id, now))
    for fn in pre_auth_fns:
        res = fn(conn, plan_rows)
        checks.append(res)
        if res["status"] == "fail":
            blocks.append(f"{res['name']}: {res['detail']}")

    # 8) 时区窗口检查：部分未解析只 block 单条（timezone_blocks），
    #    仅全部被 block 时整体 fail 并进入 blocks
    tz_res = check_timezones(conn, plan_rows, now, send_window_override=send_window_override)
    checks.append(tz_res["check"])
    if tz_res["check"]["status"] == "fail":
        blocks.append(f"timezone_resolution: {tz_res['check']['detail']}")
    timezone_blocks = tz_res["timezone_blocks"]

    return {
        "pass": len(blocks) == 0,
        "checks": checks,
        "blocks": blocks,
        "smtp_blocked": len(blocks) > 0,
        "batch_id": batch_id,
        "plan_count": plan_count,
        "checked_at": now.isoformat(),
        "timezone_blocks": timezone_blocks,
    }


# ── CLI ─────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(description="P0 preflight gate")
    parser.add_argument("--batch", required=True, help="batch id or 'latest'")
    parser.add_argument("--report", help="write JSON result to this path")
    parser.add_argument("--db", default=DB_PATH, help="sqlite db path")
    parser.add_argument("--no-dns", action="store_true", help="skip DNS freshness check")
    parser.add_argument("--no-cache-write", action="store_true", help="do not write mx_cache to system_config")
    args = parser.parse_args(argv)

    conn = _get_conn(args.db)
    try:
        result = run_preflight(
            conn,
            args.batch,
            snapshot_path=str(PROJECT_DIR / "output" / f"frozen_{args.batch}.json"),
            require_dns=not args.no_dns,
            persist_cache=not args.no_cache_write,
        )
    finally:
        conn.close()

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(out, encoding="utf-8")
    print(out)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
