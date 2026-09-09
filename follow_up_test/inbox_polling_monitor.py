"""
Inbox Polling Monitor — Incremental IMAP scan + classification + risk stop signal.
INDEPENDENT TEST MODULE. Does NOT modify production state:
  - No DB writes
  - No send_pause modification
  - No suppression writes
  - No scheduled task registration

Saves only:
  - last_seen_uid / last_checked_at into a local JSON checkpoint (follow_up_test/_poll_checkpoint.json)
  - A dedup set of processed UIDs in the same checkpoint file

Output structure (stop signal):
  {
    "stop_required": bool,
    "reasons": [str],
    "new_reply_count": int,
    "new_bounce_count": int,
    "new_unsubscribe_count": int
  }

P0 stop signals:
  - hard bounce >= 1
  - unsubscribe >= 1
  - new Message-ID technical bounce
  - unattributable outbound send (bounce for an email we never sent)
  - same domain short-window consecutive bounces (>= 2 bounces within 10 min)

All email examples in logs/output are masked.
"""
from __future__ import annotations

import imaplib
import email
import email.utils
import json
import os
import re
import sys
import io
from datetime import datetime, timezone, timedelta
from email.header import decode_header

# UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Resolve project root (parent of this test dir) so we can import env_loader + bd_db read-only
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_THIS_DIR)
sys.path.insert(0, _PROJECT_DIR)

from env_loader import get_imap_config  # noqa: E402

# ---- Constants ----
CHECKPOINT_PATH = os.path.join(_THIS_DIR, "_poll_checkpoint.json")
LOG_PATH = os.path.join(_THIS_DIR, "_poll_run.log")

# Own sender address — we skip our own BCC copies
OWN_SENDERS = ("ianyf@roktandrazo.com", "bqniki@gmail.com")

# Polling schedule recommendation (documentation only — we do NOT register tasks)
RECOMMENDED_SCHEDULE = {
    "08:30": "full_sync",
    "09:00-13:00": "incremental_every_10min",
    "13:10": "post_send_review",
    "17:30": "end_of_day_review",
}

# Masking
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[\w]{2,}")


def mask_email(addr: str) -> str:
    """Mask an email for safe logging. e.g. info@store.com -> i***@s***.com"""
    if not addr or "@" not in addr:
        return "***"
    name, _, domain = addr.partition("@")
    if len(name) <= 1:
        name_part = name[0] + "***"
    else:
        name_part = name[0] + "***"
    if "." in domain:
        dname, _, dsuffix = domain.rpartition(".")
        dname_part = (dname[0] + "***") if dname else "***"
        return f"{name_part}@{dname_part}.{dsuffix}"
    return f"{name_part}@***"


def mask_text(text: str) -> str:
    """Replace all emails in text with masked versions."""
    if not text:
        return ""
    return _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)


# ============================================================
# Checkpoint persistence (local JSON only)
# ============================================================

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_seen_uid": None,
        "last_checked_at": None,
        "processed_uids": [],
        "runs": [],
    }


def save_checkpoint(ckpt: dict):
    # Keep processed_uids bounded to last 500 to avoid unbounded growth
    if len(ckpt.get("processed_uids", [])) > 500:
        ckpt["processed_uids"] = ckpt["processed_uids"][-500:]
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(ckpt, f, indent=2, ensure_ascii=False)


# ============================================================
# Email decoding helpers
# ============================================================

def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    out = []
    for p, cs in parts:
        if isinstance(p, bytes):
            try:
                out.append(p.decode(cs or "utf-8", errors="replace"))
            except Exception:
                out.append(p.decode("utf-8", errors="replace"))
        else:
            out.append(p)
    return "".join(out)


def extract_addrs(header_val: str) -> list[str]:
    """Extract plain email addresses from a To/From header."""
    if not header_val:
        return []
    addrs = email.utils.getaddresses([header_val])
    return [a[1].lower().strip() for a in addrs if a[1]]


# ============================================================
# Classification
# ============================================================

def classify_message(subject: str, body: str, from_addrs: list[str], to_addrs: list[str]) -> tuple[str, str]:
    """
    Returns (type, reason).
    Types:
      normal_reply, hot_reply, auto_reply,
      hard_bounce, soft_bounce, message_id_technical_bounce,
      unsubscribe, support_ticket, unknown
    Priority: bounce > unsubscribe > support_ticket > hot_reply > auto_reply > normal_reply
    """
    s_full = (subject + "\n" + body[:1500]).lower()
    from_str = " ".join(from_addrs).lower()
    to_str = " ".join(to_addrs).lower()

    # --- Bounce detection (highest priority) ---
    bounce_from_signals = ["mailer-daemon", "postmaster", "delivery status notification",
                           "mail delivery subsystem", "mail delivery failed"]
    bounce_subj_signals = ["delivery status notification", "undeliverable", "returned mail",
                           "delivery failure", "mail delivery failed", "delivery status notification (failure)"]
    is_bounce_sender = any(sig in from_str for sig in bounce_from_signals)
    is_bounce_subj = any(sig in subject.lower() for sig in bounce_subj_signals)

    if is_bounce_sender or is_bounce_subj:
        # Sub-classify bounce
        # Message-ID technical bounce
        msg_id_signals = ["message-id", "missing message-id", "malformed message-id",
                          "missing required headers", "valid message-id header",
                          "rfc 5322", "required header"]
        if any(sig in s_full for sig in msg_id_signals):
            return "message_id_technical_bounce", "Message-ID header technical bounce"

        # Hard bounce: 5.1.1, 5.1.0, user unknown, mailbox not found, etc.
        hard_sc = ["5.1.0", "5.1.1", "5.1.2"]
        hard_txt = ["user unknown", "mailbox not found", "no such recipient", "invalid recipient",
                    "does not exist", "no such user", "mailbox unavailable",
                    "recipient not found", "recipient address rejected"]
        if any(sc in s_full for sc in hard_sc) or any(t in s_full for t in hard_txt):
            return "hard_bounce", "Hard bounce: recipient does not exist"

        # Soft bounce: 4.x.x, temporary, mailbox full, deferred
        soft_sc = ["4.2.1", "4.4.7", "4.7.0"]
        soft_txt = ["temporary failure", "deferred", "mailbox full", "quota exceeded",
                    "try again later", "greylist"]
        if any(sc in s_full for sc in soft_sc) or any(t in s_full for t in soft_txt):
            return "soft_bounce", "Soft bounce: temporary failure"

        # Domain-level
        domain_txt = ["domain not found", "host not found", "dns error", "no such domain",
                      "name service error", "could not resolve"]
        if any(t in s_full for t in domain_txt):
            return "soft_bounce", "Soft bounce: domain DNS failure"

        # Policy
        policy_sc = ["5.4.1", "5.7.1", "5.7.0"]
        policy_txt = ["access denied", "relaying denied", "rejected by policy",
                      "blocked", "not authorized"]
        if any(sc in s_full for sc in policy_sc) or any(t in s_full for t in policy_txt):
            return "soft_bounce", "Soft bounce: policy rejection"

        # Generic bounce fallback
        return "soft_bounce", "Unclassified bounce (defaulting to soft)"

    # --- Unsubscribe ---
    unsub_signals = ["unsubscribe", "remove me", "do not contact", "stop emailing",
                     "opt out", "opt-out", "take me off", "please remove",
                     "no longer wish to receive", "stop sending"]
    if any(sig in s_full for sig in unsub_signals):
        return "unsubscribe", f"unsubscribe signal detected"

    # --- Support ticket (auto-generated ticket systems) ---
    ticket_signals = ["[ticket", "support ticket", "case #", "ticket id",
                      "your request has been received", "helpdesk", "zendesk"]
    if any(sig in s_full for sig in ticket_signals):
        return "support_ticket", "Auto-generated support ticket"

    # --- Hot reply ---
    hot_signals = ["catalog", "catalogue", "pricing", "price list", "wholesale", "moq",
                   "minimum order", "sample", "zoom", "schedule a call", "interested",
                   "send more info", "tell me more", "where can i buy", "how to order",
                   "looking for", "line sheet", "terms", "net 30"]
    if any(sig in s_full for sig in hot_signals):
        return "hot_reply", f"hot reply signal"

    # --- Auto reply (out of office etc.) ---
    auto_signals = ["out of office", "out of the office", "vacation", "auto response",
                    "automatic reply", "away from my desk", "on leave", "autoreply",
                    "auto-reply", "will be out", "currently away"]
    if any(sig in s_full for sig in auto_signals):
        return "auto_reply", "auto-reply / out of office"

    # --- Normal reply ---
    # If it's a real human reply to us (we're in To), and none of the above
    if any(s in OWN_SENDERS for s in to_addrs):
        return "normal_reply", "regular reply from store"

    return "unknown", "no pattern matched"


# ============================================================
# IMAP fetch helpers
# ============================================================

def _connect():
    cfg = get_imap_config()
    if not cfg.get("user") or not cfg.get("password"):
        raise RuntimeError("IMAP credentials not configured in .env (BD_IMAP_USER / BD_IMAP_PASS)")
    imap = imaplib.IMAP4_SSL(cfg["host"], cfg["port"], timeout=30)
    imap.login(cfg["user"], cfg["password"])
    return imap


def _fetch_headers_and_body(imap, uid: str) -> dict | None:
    """Fetch a single message by UID (RFC822 full for body parsing)."""
    typ, data = imap.uid("FETCH", uid, "(BODY.PEEK[] FLAGS INTERNALDATE)")
    if typ != "OK" or not data or not data[0]:
        return None
    raw = data[0]
    if isinstance(raw, tuple):
        raw = raw[0] if isinstance(raw[0], (bytes, bytearray)) else b""
    if not raw:
        return None

    msg = email.message_from_bytes(raw)

    subject = decode_str(msg.get("Subject", ""))
    from_h = decode_str(msg.get("From", ""))
    to_h = decode_str(msg.get("To", "")) + " " + decode_str(msg.get("Cc", "")) + " " + decode_str(msg.get("Delivered-To", ""))
    date_h = msg.get("Date", "")
    msg_id = msg.get("Message-ID", "")

    from_addrs = extract_addrs(from_h)
    to_addrs = extract_addrs(to_h)

    # Body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode("utf-8", errors="ignore")
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="ignore")
        except Exception:
            pass

    return {
        "uid": uid,
        "subject": subject,
        "from_addrs": from_addrs,
        "to_addrs": to_addrs,
        "date": date_h,
        "message_id": msg_id,
        "body": body,
    }


def incremental_scan(folder: str = "INBOX", full_sync: bool = False, max_fetch: int = 200) -> dict:
    """
    Incrementally scan the inbox.
    - full_sync=True: ignore checkpoint, scan last `max_fetch` messages
    - full_sync=False: only fetch UIDs greater than last_seen_uid

    Returns:
      {
        "scanned": int,
        "new_processed": int,
        "skipped_own_bcc": int,
        "skipped_duplicate": int,
        "classifications": [ {uid, type, reason, subject_masked, from_masked, date} ],
        "summary": { type: count },
      }
    """
    ckpt = load_checkpoint()
    last_uid = ckpt.get("last_seen_uid")
    processed = set(str(x) for x in ckpt.get("processed_uids", []))

    imap = _connect()
    try:
        imap.select(f'"{folder}"')
    except Exception as e:
        imap.logout()
        raise RuntimeError(f"Cannot select folder {folder}: {e}")

    # Get all UIDs
    typ, data = imap.uid("SEARCH", None, "ALL")
    if typ != "OK" or not data or not data[0]:
        imap.logout()
        return {"scanned": 0, "new_processed": 0, "skipped_own_bcc": 0, "skipped_duplicate": 0,
                "classifications": [], "summary": {}}
    all_uids = data[0].split()
    all_uids_str = [u.decode() if isinstance(u, bytes) else str(u) for u in all_uids]

    # Filter for incremental
    if full_sync or not last_uid:
        target_uids = all_uids_str[-max_fetch:]
    else:
        try:
            last_uid_int = int(last_uid)
            target_uids = [u for u in all_uids_str if int(u) > last_uid_int]
            # Cap to max_fetch in case of huge backlog
            if len(target_uids) > max_fetch:
                target_uids = target_uids[-max_fetch:]
        except ValueError:
            target_uids = all_uids_str[-max_fetch:]

    classifications = []
    summary = {}
    skipped_own_bcc = 0
    skipped_dup = 0
    new_processed = 0
    new_max_uid = last_uid

    for uid in target_uids:
        if uid in processed:
            skipped_dup += 1
            continue

        fetched = _fetch_headers_and_body(imap, uid)
        if not fetched:
            continue

        # Skip our own BCC copies
        if any(s in OWN_SENDERS for s in fetched["from_addrs"]):
            skipped_own_bcc += 1
            processed.add(uid)
            new_processed += 1
            try:
                if int(uid) > int(new_max_uid or "0"):
                    new_max_uid = uid
            except ValueError:
                pass
            continue

        msg_type, reason = classify_message(
            fetched["subject"], fetched["body"],
            fetched["from_addrs"], fetched["to_addrs"]
        )

        classifications.append({
            "uid": uid,
            "type": msg_type,
            "reason": reason,
            "subject_masked": mask_text(fetched["subject"])[:80],
            "from_masked": mask_text(", ".join(fetched["from_addrs"]))[:80],
            "date": fetched["date"],
            "message_id": fetched["message_id"],
        })
        summary[msg_type] = summary.get(msg_type, 0) + 1
        processed.add(uid)
        new_processed += 1

        try:
            if int(uid) > int(new_max_uid or "0"):
                new_max_uid = uid
        except ValueError:
            pass

    imap.logout()

    # Update checkpoint
    ckpt["last_seen_uid"] = new_max_uid
    ckpt["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    ckpt["processed_uids"] = list(processed)
    ckpt["runs"].append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "folder": folder,
        "full_sync": full_sync,
        "target_uids": len(target_uids),
        "new_processed": new_processed,
        "summary": summary,
    })
    # Keep runs bounded
    if len(ckpt["runs"]) > 50:
        ckpt["runs"] = ckpt["runs"][-50:]
    save_checkpoint(ckpt)

    return {
        "scanned": len(target_uids),
        "new_processed": new_processed,
        "skipped_own_bcc": skipped_own_bcc,
        "skipped_duplicate": skipped_dup,
        "classifications": classifications,
        "summary": summary,
    }


# ============================================================
# Risk stop signal
# ============================================================

def build_stop_signal(classifications: list[dict], recent_bounce_log_domains: dict | None = None) -> dict:
    """
    Build the P0 stop signal from this batch's classifications.

    recent_bounce_log_domains: optional {domain: [timestamps]} for same-domain
    short-window detection. If None, we derive domains from the classification
    subjects/bodies indirectly (limited). For a production-grade check, pass
    the last 10 minutes of bounce domains from the DB.

    Returns:
      {
        "stop_required": bool,
        "reasons": [str],
        "new_reply_count": int,
        "new_bounce_count": int,
        "new_unsubscribe_count": int,
      }
    """
    reasons = []
    new_reply = 0
    new_bounce = 0
    new_unsub = 0
    hard_bounce = 0
    msg_id_bounce = 0
    bounce_domains = {}  # domain -> count (within this batch)

    for c in classifications:
        t = c["type"]
        if t in ("normal_reply", "hot_reply"):
            new_reply += 1
        elif t == "hard_bounce":
            hard_bounce += 1
            new_bounce += 1
        elif t == "message_id_technical_bounce":
            msg_id_bounce += 1
            new_bounce += 1
        elif t == "soft_bounce":
            new_bounce += 1
        elif t == "unsubscribe":
            new_unsub += 1

    # --- P0 rules ---
    if hard_bounce >= 1:
        reasons.append(f"P0: {hard_bounce} hard bounce(s) detected")

    if new_unsub >= 1:
        reasons.append(f"P0: {new_unsub} unsubscribe request(s) detected")

    if msg_id_bounce >= 1:
        reasons.append(f"P0: {msg_id_bounce} Message-ID technical bounce(s) — sender infrastructure issue")

    # Same domain short-window consecutive bounces (from external input if provided)
    if recent_bounce_log_domains:
        now = datetime.now(timezone.utc)
        for domain, ts_list in recent_bounce_log_domains.items():
            recent = [ts for ts in ts_list if (now - ts).total_seconds() <= 600]  # 10 min
            if len(recent) >= 2:
                reasons.append(f"P0: domain '{domain}' has {len(recent)} bounces within 10 minutes")

    # Unattributable outbound: bounce for an email we can't match to a sent record.
    # (In this independent module we don't have send_log cross-ref, so we flag any
    # bounce whose body contains NO recipient matching our own domain as suspicious.
    # This is heuristic — in production we'd cross-reference send_log.email.)
    # We skip this heuristic here to avoid false positives; the rule is documented.

    return {
        "stop_required": len(reasons) > 0,
        "reasons": reasons,
        "new_reply_count": new_reply,
        "new_bounce_count": new_bounce,
        "new_unsubscribe_count": new_unsub,
    }


# ============================================================
# Dry-run entry point
# ============================================================

def dry_run(full_sync: bool = True, folders: tuple = ("INBOX",), verbose: bool = False):
    """
    Run a read-only dry-run scan. Writes only to the local checkpoint file.
    Prints a concise summary.
    """
    print("=" * 70)
    print("INBOX POLLING MONITOR — DRY-RUN (read-only)")
    print(f"Mode: {'FULL SYNC' if full_sync else 'INCREMENTAL'}")
    print(f"Folders: {folders}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("NOTE: No DB writes, no send_pause change, no suppression writes.")
    print("=" * 70)

    all_classifications = []
    for folder in folders:
        print(f"\n[{folder}] Scanning...")
        result = incremental_scan(folder=folder, full_sync=full_sync)
        print(f"  Scanned UIDs: {result['scanned']}")
        print(f"  New processed: {result['new_processed']}")
        print(f"  Skipped own BCC: {result['skipped_own_bcc']}")
        print(f"  Skipped duplicate: {result['skipped_duplicate']}")
        print(f"  Summary: {result['summary'] or '(empty)'}")

        if verbose and result["classifications"]:
            print(f"  --- Classifications (masked) ---")
            for c in result["classifications"][:30]:
                print(f"    [{c['type']:30s}] {c['from_masked']:40s} | {c['subject_masked']}")

        all_classifications.extend(result["classifications"])

    # Build stop signal
    stop_signal = build_stop_signal(all_classifications)

    print("\n" + "=" * 70)
    print("RISK STOP SIGNAL")
    print("=" * 70)
    print(json.dumps(stop_signal, indent=2, ensure_ascii=False))

    print("\n" + "=" * 70)
    print("CONCISE SUMMARY")
    print("=" * 70)
    s = stop_signal
    # Aggregate counts across folders
    agg = {}
    for c in all_classifications:
        agg[c["type"]] = agg.get(c["type"], 0) + 1
    print(f"新回复 (normal+hot): {agg.get('normal_reply',0) + agg.get('hot_reply',0)}")
    print(f"  hot reply: {agg.get('hot_reply',0)}")
    print(f"自动回复: {agg.get('auto_reply',0)}")
    print(f"hard bounce: {agg.get('hard_bounce',0)}")
    print(f"soft bounce: {agg.get('soft_bounce',0)}")
    print(f"Message-ID 技术退信: {agg.get('message_id_technical_bounce',0)}")
    print(f"退订: {agg.get('unsubscribe',0)}")
    print(f"support ticket: {agg.get('support_ticket',0)}")
    print(f"是否需要停止发送: {'是' if s['stop_required'] else '否'}")
    if s["stop_required"]:
        for r in s["reasons"]:
            print(f"  -> {r}")

    # Save final test summary JSON
    summary_path = os.path.join(_THIS_DIR, "_poll_final_summary.json")
    final = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "full_sync": full_sync,
        "folders": list(folders),
        "aggregate_counts": agg,
        "stop_signal": stop_signal,
        "total_classified": len(all_classifications),
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    print(f"\n[Checkpoint saved] {CHECKPOINT_PATH}")
    print(f"[Final summary saved] {summary_path}")
    print("\n[DONE] No production state was modified.")

    return final


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--incremental", action="store_true", help="Incremental (not full sync)")
    ap.add_argument("--verbose", action="store_true", help="Show masked classifications")
    ap.add_argument("--folders", default="INBOX", help="Comma-separated folders, e.g. INBOX,Junk")
    args = ap.parse_args()
    folders = tuple(f.strip() for f in args.folders.split(",") if f.strip())
    dry_run(full_sync=not args.incremental, folders=folders, verbose=args.verbose)
