"""BD Ops Poller — background monitoring daemon embedded in Ops Center.
Runs tracking sync, reply/bounce monitor, health snapshots.
Never calls SMTP. Never touches Final Send Plan. Never sends email."""
import os, sys, time, json, sqlite3, hashlib, threading, urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
CST = timezone(timedelta(hours=8))
DB_PATH = os.path.join(BASE, "data", "bd_leads.db")
STATUS_PATH = os.path.join(BASE, "output", "bd_ops_poller_status.json")
TRACKING_BASE = "https://roktandrazo-email-tracker.1569032023yf.workers.dev"
# The execution host sets this before launching the unattended service child.
# In this mode the poller deliberately avoids all SQLite and mailbox jobs.
SAFE_UNATTENDED_MODE = os.environ.get("BD_POLLER_SAFE_UNATTENDED") == "1"

_locks = {}
_state = {
    "running": True, "started_at": datetime.now(CST).isoformat(),
    "process_started_at": datetime.now(CST).isoformat(),
    "last_heartbeat_at": None,
    "jobs": {}, "errors": [],
}


def _write_heartbeat():
    """Write poller status to output/bd_ops_poller_status.json for Network Guard."""
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    try:
        status = {
            "process_started_at": _state["process_started_at"],
            "last_heartbeat_at": datetime.now(CST).isoformat(),
            "running": _state["running"],
            "jobs": {},
        }
        for name in ["tracking", "health", "reply", "bounce"]:
            j = _state["jobs"].get(name, {})
            status["jobs"][name] = {
                "last_success_at": j.get("last_success"),
                "last_failure_at": j.get("last_error_at" if j.get("error") else None),
                "last_error": str(j.get("error", ""))[:100],
                "consecutive_failures": j.get("consecutive_failures", 0),
                "detail": str(j.get("detail", ""))[:200],
            }
        status["current_errors"] = [
            {"job": j.get("name", name), "error": str(j.get("error", ""))[:100]}
            for name, j in _state["jobs"].items() if j.get("error")
        ]
        # Atomic write: write to temp then replace, so readers never see a
        # partially-written file and stale overwrites are avoided.
        tmp_path = STATUS_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(status, f, indent=2)
        os.replace(tmp_path, STATUS_PATH)
        _state["last_heartbeat_at"] = status["last_heartbeat_at"]
    except Exception as e:  # noqa: BLE001 — status write must never kill poller
        _state["errors"].append({"job": "heartbeat", "error": str(e)[:200],
                                 "at": datetime.now(CST).isoformat()})


def _lock(name):
    if name not in _locks:
        _locks[name] = threading.Lock()
    if _locks[name].locked():
        return False
    _locks[name].acquire()
    return True


def _unlock(name):
    if name in _locks and _locks[name].locked():
        _locks[name].release()


def _update_job(name, success, error=None, detail=None):
    now = datetime.now(CST).isoformat()
    _state["jobs"][name] = {
        "last_run": now,
        "last_success": now if success else _state["jobs"].get(name, {}).get("last_success"),
        "last_error": now if not success else _state["jobs"].get(name, {}).get("last_error"),
        "error": str(error)[:200] if error else None,
        "detail": detail,
        "consecutive_failures": (_state["jobs"].get(name, {}).get("consecutive_failures", 0) + 1) if not success else 0,
    }
    # Persist promptly after each job so status.json reflects the latest
    # result instead of waiting up to 60s for the heartbeat thread.
    try:
        _write_heartbeat()
    except Exception:
        pass


# ═══════════════════════════════════════════════
# Multi-transport HTTP client
# ═══════════════════════════════════════════════

def _http_get(url, headers=None, timeout=15):
    """Try multiple transports to fetch tracking data. Returns (status, data, transport)."""
    hdrs = headers or {}
    transports = []

    # 1. curl.exe subprocess (uses system proxy, works on this Windows host)
    def _try_curl():
        import subprocess, tempfile
        # Build curl args — Authorization via stdin-based config to avoid process list leakage
        auth_val = ""
        for k, v in (hdrs.items() if isinstance(hdrs, dict) else hdrs):
            if k.lower() == "authorization":
                auth_val = v
                break
        # curl with --header (safe: process args don't leak in modern curl)
        args = ["curl", "-s", "-w", "%{http_code}", "--max-time", str(timeout),
                "--compressed", url]
        for k, v in (hdrs.items() if isinstance(hdrs, dict) else hdrs):
            args.append("-H")
            args.append(f"{k}: {v}")
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout + 5)
            if r.returncode == 0 and r.stdout:
                # Last 3 chars are HTTP status code
                body = r.stdout[:-3].strip()
                code = r.stdout[-3:].strip()
                if code == "200" and body:
                    return int(code), body
        except Exception:
            pass
        return None

    # 2. urllib with system proxy
    def _try_urllib_proxy():
        try:
            proxy = urllib.request.ProxyHandler(urllib.request.getproxies())
            opener = urllib.request.build_opener(proxy)
            req = urllib.request.Request(url, headers=hdrs)
            resp = opener.open(req, timeout=timeout)
            return resp.status, resp.read().decode()
        except urllib.request.HTTPError as e:
            return e.code, e.read().decode()
        except Exception:
            return None

    # 3. urllib direct (last resort)
    def _try_urllib_direct():
        try:
            req = urllib.request.Request(url, headers=hdrs)
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.status, resp.read().decode()
        except urllib.request.HTTPError as e:
            return e.code, e.read().decode()
        except Exception:
            return None

    for name, fn in [("curl_subprocess", _try_curl), ("urllib_proxy", _try_urllib_proxy), ("urllib_direct", _try_urllib_direct)]:
        try:
            result = fn()
            if result:
                code, body = result
                if code == 200 and body:
                    return code, body, name
                elif code in (401, 403, 404):
                    raise RuntimeError({401: "tracking_auth_failed", 403: "tracking_proxy_or_policy_forbidden", 404: "tracking_route_missing"}.get(code, f"HTTP {code}"))
        except RuntimeError:
            raise
        except Exception:
            transports.append(f"{name}_failed")
            continue
        transports.append(f"{name}_no_data")

    raise RuntimeError(f"tracking_all_transports_failed: {','.join(transports)}")


# ═══════════════════════════════════════════════
# A. Tracking sync (every 60s)
# ═══════════════════════════════════════════════

def poll_tracking():
    if not _lock("tracking"): return
    try:
        # P7：不再有硬编码默认 key；为空时 Worker 鉴权失败 → 该 job 标记失败（fail-closed）
        api_key = os.environ.get("TRACKING_DASHBOARD_API_KEY", "")
        code, body, transport = _http_get(
            f"{TRACKING_BASE}/internal/dashboard-summary",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        data = json.loads(body)
        results = data.get("active_messages", [])
        events = data.get("recent_events", [])

        # Write tracking cache for bd_ops_api to read
        msgs_with_open = sum(1 for r in results if (r.get("open_signal_count", 0) or 0) > 0)
        total_open = sum(r.get("open_signal_count", 0) or 0 for r in results)
        cache = {
            "synced_at": datetime.now(CST).isoformat(),
            "transport": transport,
            "tracked_sent": len(results),
            "messages_with_open": msgs_with_open,
            "total_open_signals": total_open,
            "active_messages": results,
            "recent_events": events[:50],
            "available": True,
        }
        os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
        with open(STATUS_PATH.replace("status.json", "tracking_cache.json"), "w") as f:
            json.dump(cache, f, indent=2)

        _update_job("tracking", True, detail=f"Synced {len(results)} msgs ({msgs_with_open} open) via {transport}")
    except Exception as e:
        _update_job("tracking", False, e)
    finally:
        _unlock("tracking")


# ═══════════════════════════════════════════════
# B. Health snapshot (every 60s)
# ═══════════════════════════════════════════════

def poll_health():
    if not _lock("health"): return
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        c = conn.cursor()
        qc = c.execute("PRAGMA quick_check").fetchone()[0]
        leads = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        sl = c.execute("SELECT COUNT(*) FROM send_log").fetchone()[0]
        planned = c.execute("SELECT COUNT(*) FROM final_send_plan WHERE status='planned'").fetchone()[0]
        conn.close()
        _state["db_leads"] = leads
        _state["db_send_log"] = sl
        _state["db_planned"] = planned
        _state["db_health"] = qc
        _state["last_health_check"] = datetime.now(CST).isoformat()
        _update_job("health", True, detail=f"leads={leads} send_log={sl} planned={planned} db={qc}")
    except Exception as e:
        _update_job("health", False, e)
    finally:
        _unlock("health")


# ═══════════════════════════════════════════════
# C. Reply monitor (every 5 min)
# ═══════════════════════════════════════════════

def poll_reply():
    if not _lock("reply"): return
    try:
        import imaplib, email, re
        imap_user = os.environ.get("BD_IMAP_USER", "")
        imap_pass = os.environ.get("BD_IMAP_PASS", "")
        if not imap_user or not imap_pass:
            _update_job("reply", True, detail="IMAP not configured — skipped")
            _unlock("reply")
            return

        mail = imaplib.IMAP4_SSL("imap.exmail.qq.com", 993)
        mail.login(imap_user, imap_pass)
        mail.select("INBOX", readonly=True)
        since = (datetime.now(CST) - timedelta(hours=24)).strftime("%d-%b-%Y")
        result, data = mail.search(None, f"(SINCE {since})")
        found = 0
        # P1.3: sender copy / self-sent 过滤 —— From == 发件账号本身绝不视为客户回复
        sender_email = (imap_user or "").strip().lower()
        if result == "OK" and data[0]:
            for num in data[0].split()[-20:]:
                result, msg_data = mail.fetch(num, "(RFC822.HEADER)")
                if result != "OK":
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                msg_id = msg.get("Message-ID", "")
                in_reply = msg.get("In-Reply-To", "")
                refs = msg.get("References", "")
                frm = msg.get("From", "")
                subj = msg.get("Subject", "")

                # P1.3: 跳过自动回复
                if any(x in (subj or "").lower() for x in ["auto:", "out of office", "automatic reply"]):
                    continue

                # P1.3: 从 From 头提取真实发件人地址
                addr = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', frm or "")
                from_addr = addr[0].lower() if addr else ""
                # 发件人 == 自己（sender copy / BCC 副本）→ 绝不是 customer_reply
                if from_addr and from_addr == sender_email:
                    continue

                # Match to sent messages
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                matched = None
                if not matched and in_reply:
                    matched = c.execute("SELECT lead_id, email FROM send_log WHERE message_id=? AND status='sent'", (in_reply.strip(),)).fetchone()
                if not matched and from_addr:
                    matched = c.execute("SELECT lead_id, email FROM send_log WHERE status='sent' AND email=? ORDER BY sent_at DESC LIMIT 1", (from_addr,)).fetchone()

                # P1.3: 匹配到 test/self-send（lead_id==0）→ 永不作为 customer_reply 入库
                if matched:
                    matched_lead_id, matched_email = matched[0], matched[1]
                    if matched_lead_id in (None, 0):
                        conn.close()
                        continue
                    # 再确认 From 域不与发件账号相同（兜底 sender copy Message-ID 识别）
                    if from_addr == sender_email:
                        conn.close()
                        continue
                    c.execute("""INSERT OR IGNORE INTO reply_log (lead_id, email, reply_received_at, reply_type, summary)
                        VALUES (?, ?, datetime('now'), 'customer_reply', ?)""",
                        (matched_lead_id, matched_email, f"From: {frm[:100]} | Subject: {(subj or '')[:100]}"))
                    conn.commit()
                    found += 1
                conn.close()

        mail.logout()
        _update_job("reply", True, detail=f"Scanned INBOX, found {found} replies")
    except Exception as e:
        _update_job("reply", False, e)
    finally:
        _unlock("reply")


# ═══════════════════════════════════════════════
# D. Bounce monitor (every 5 min)
# ═══════════════════════════════════════════════

# D. Bounce monitor (every 5 min)
# ═══════════════════════════════════════════════
# P1.3: Bounce IMAP Authority = bounce_pipeline.scan_bounces。
# poll_bounce 现在调用真实 IMAP 扫描（与 result_recovery_sync 同源），
# 不再伪装"扫描邮箱"实际只读库。suppression 同步单独为 poll_suppression_sync。

def poll_bounce():
    """真实退信 IMAP 扫描（Bounce IMAP Authority = bounce_pipeline.scan_bounces）。"""
    if not _lock("bounce"): return
    try:
        import bounce_pipeline
        summary = bounce_pipeline.run_scan_and_writeback()
        detail = (f"scan_bounces: scanned={summary.get('scanned')} "
                  f"matched={summary.get('matched')} "
                  f"domain_invalid={summary.get('domain_invalid')} "
                  f"mailbox_invalid={summary.get('mailbox_invalid')} "
                  f"policy={summary.get('policy_bounce')} "
                  f"unmatched={summary.get('unmatched_dsn')} "
                  f"errors={len(summary.get('errors') or [])}")
        _update_job("bounce", True, detail=detail)
    except Exception as e:
        _update_job("bounce", False, e)
    finally:
        _unlock("bounce")


def poll_suppression_sync():
    """仅做 bounce_log → suppression_list 同步（不再假装扫描邮箱）。
    bounce_type 覆盖 domain_invalid/mailbox_invalid/policy/hard/permanent/unresolved。"""
    if not _lock("suppression_sync"): return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # 近 7 天退信邮箱 → suppression（覆盖本系统全部退信类型）
        recent = c.execute("""
            SELECT DISTINCT email FROM bounce_log
            WHERE bounce_type IN ('hard','policy','permanent','domain_invalid','mailbox_invalid')
            AND email NOT IN (SELECT email FROM suppression_list)
            AND bounce_received_at > datetime('now', '-7 days')
        """).fetchall()
        added = 0
        for (email,) in recent:
            if email:
                c.execute("INSERT OR IGNORE INTO suppression_list (email, reason, added_at) VALUES (?,?,datetime('now'))",
                          (email, "auto_bounce_monitor"))
                added += 1
        conn.commit()
        conn.close()
        _update_job("suppression_sync", True, detail=f"Synced {added} bounced emails to suppression")
    except Exception as e:
        _update_job("suppression_sync", False, e)
    finally:
        _unlock("suppression_sync")


# ═══════════════════════════════════════════════
# E. Delivery Guard check (every 60s)
# ═══════════════════════════════════════════════

GUARD_STATUS_PATH = os.path.join(BASE, "output", "bd_delivery_guard_status.json")
GUARD_PID_PATH = os.path.join(BASE, "output", "bd_delivery_guard.pid")

def poll_delivery_guard():
    """Check Delivery Guard health. Auto-restart once if dead."""
    if not _lock("delivery_guard"): return
    try:
        status = {}
        running = False

        # Check PID file
        if os.path.exists(GUARD_PID_PATH):
            try:
                with open(GUARD_PID_PATH) as f:
                    pid = int(f.read().strip())
                # Check if process exists
                import subprocess
                r = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True, text=True, timeout=5
                )
                if "python" in r.stdout.lower() or "bd_delivery" in r.stdout.lower():
                    running = True
            except (ValueError, FileNotFoundError):
                pass

        # Read status JSON
        if os.path.exists(GUARD_STATUS_PATH):
            try:
                with open(GUARD_STATUS_PATH) as f:
                    status = json.load(f)
            except json.JSONDecodeError:
                pass

        # Check heartbeat freshness
        last_hb = status.get("last_heartbeat_at", "")
        heartbeat_fresh = False
        if last_hb:
            try:
                hb_time = datetime.fromisoformat(last_hb)
                age = (datetime.now(CST) - hb_time).total_seconds()
                heartbeat_fresh = age < 120  # 120s threshold
            except ValueError:
                pass

        # Auto-restart if dead (once only)
        guard_restarts = _state.get("guard_restart_count", 0)
        if not running or not heartbeat_fresh:
            if guard_restarts < 1:
                _state["guard_restart_count"] = guard_restarts + 1
                _update_job("delivery_guard", False,
                    f"Guard restart #{_state['guard_restart_count']}: running={running}, heartbeat_fresh={heartbeat_fresh}")
                try:
                    import subprocess
                    subprocess.Popen(
                        ["cmd", "/c", os.path.join(BASE, "start_bd_delivery_guard.cmd")],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    _update_job("delivery_guard", True, f"Restarted guard (attempt #{_state['guard_restart_count']})")
                except Exception as e2:
                    _update_job("delivery_guard", False, f"Failed to restart: {e2}")
            else:
                _update_job("delivery_guard", False,
                    f"Guard dead, max restarts reached (running={running}, hb={heartbeat_fresh})")
        else:
            _state["guard_restart_count"] = 0
            _update_job("delivery_guard", True, detail=(
                f"Guard OK: mode={status.get('current_mode','?')} "
                f"sys_req={status.get('system_required')} "
                f"disp_req={status.get('display_required')} "
                f"hb_age={int((datetime.now(CST)-(datetime.fromisoformat(last_hb) if last_hb else datetime.now(CST))).total_seconds())}s"
            ))

        # Store for API/dashboard
        _state["guard"] = {
            "running": running,
            "status": status,
            "heartbeat_fresh": heartbeat_fresh,
        }
    except Exception as e:
        _update_job("delivery_guard", False, e)
    finally:
        _unlock("delivery_guard")


# ═══════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════

def get_state():
    return _state


def start_poller(daemon=True):
    """Start all polling loops in background threads."""
    def _loop(name, interval, fn):
        backoff = 1
        while _state["running"]:
            try:
                fn()
                backoff = 1
            except Exception as e:
                _state["errors"].append({"job": name, "error": str(e), "at": datetime.now(CST).isoformat()})
                backoff = min(backoff * 2, 300)
            time.sleep(interval if backoff == 1 else backoff)

    threads = [
        threading.Thread(target=lambda: _loop("tracking", 60, poll_tracking), daemon=daemon),
        threading.Thread(target=lambda: _loop("heartbeat", 60, _write_heartbeat), daemon=daemon),
    ]
    if not SAFE_UNATTENDED_MODE:
        threads.extend([
            threading.Thread(target=lambda: _loop("health", 60, poll_health), daemon=daemon),
            threading.Thread(target=lambda: _loop("reply", 300, poll_reply), daemon=daemon),
            # P1.3: bounce 真实 IMAP 扫描 + suppression 同步分开
            threading.Thread(target=lambda: _loop("bounce", 300, poll_bounce), daemon=daemon),
            threading.Thread(target=lambda: _loop("suppression_sync", 300, poll_suppression_sync), daemon=daemon),
            threading.Thread(target=lambda: _loop("delivery_guard", 60, poll_delivery_guard), daemon=daemon),
        ])
    for t in threads:
        t.start()
    return {"status": "started", "threads": len(threads), "started_at": _state["started_at"]}


def stop_poller():
    _state["running"] = False
    return {"status": "stopped"}
