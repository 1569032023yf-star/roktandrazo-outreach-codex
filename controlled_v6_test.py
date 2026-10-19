"""Internal QA only: separate mailbox allowlist/audit; never creates customer plans.

Must be invoked by an authorized production operations entry point. Development
copies cannot send. Delivery/authentication must be checked at the receiving mailbox.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import v6_outreach

ROOT = Path(__file__).resolve().parent
POLICY_PATH = ROOT / "data" / "phase5a_internal_test_policy.json"
AUDIT_PATH = ROOT / "data" / "phase5a_internal_test_audit.sqlite3"


def load_test_policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def require_test_ready(policy, recipient, actual_sender, now=None):
    now = now or datetime.now(timezone.utc)
    if policy.get("internal_test_only") is not True or policy.get("allow_internal_without_postal_address") is not True:
        raise ValueError("CONTROLLED_INTERNAL_TEST_SCOPE_REQUIRED")
    if policy.get("controlled_test_recipients") != [recipient] or not policy.get("test_ownership_reference"):
        raise ValueError("CONTROLLED_TEST_SINGLE_RECIPIENT_REQUIRED")
    if not actual_sender or policy.get("verified_from_email") != actual_sender:
        raise ValueError("CONTROLLED_TEST_SENDER_IDENTITY_REQUIRED")
    approved = datetime.fromisoformat(policy["authorized_at"])
    if approved.tzinfo is None or not timedelta(0) <= now - approved <= timedelta(hours=24):
        raise ValueError("CONTROLLED_TEST_AUTHORIZATION_EXPIRED")
    if not policy.get("test_run_id"):
        raise ValueError("CONTROLLED_TEST_RUN_ID_REQUIRED")


def send_internal_tests(*, send=False):
    """Default is preview. SMTP Accepted is not inbox/delivery/authentication success."""
    policy = load_test_policy()
    recipients = policy.get("controlled_test_recipients") or []
    if len(recipients) != 1:
        raise ValueError("CONTROLLED_TEST_SINGLE_RECIPIENT_REQUIRED")
    recipient = recipients[0]
    messages = [v6_outreach.render_internal_test(key, recipient, policy) for key in v6_outreach.TEMPLATES]
    if not send:
        return {"status": "PREVIEW_ONLY", "messages": messages, "smtp_attempts": 0}
    if (ROOT / ".development-copy").exists():
        raise ValueError("DEVELOPMENT_INTERNAL_SMTP_BLOCKED_USE_AUTHORIZED_OPERATIONS_ENTRYPOINT")
    from bd_sender import _build_email, _create_connection
    from env_loader import get_sender_info
    sender = get_sender_info()["email"]
    require_test_ready(policy, recipient, sender)
    results = []
    for item in messages:
        # Durable reservation survives ambiguous SMTP outcomes; no automatic retries.
        with closing(sqlite3.connect(AUDIT_PATH)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS internal_tests (test_run_id TEXT, template_id TEXT, "
                "content_sha256 TEXT, reserved_at TEXT, smtp_accepted_at TEXT, message_id TEXT, PRIMARY KEY(test_run_id,template_id))")
            conn.execute("INSERT INTO internal_tests VALUES (?,?,?,?,NULL,NULL)", (policy["test_run_id"], item["template_id"],
                hashlib.sha256(json.dumps([item['subject'],item['body_text'],item['body_html']]).encode()).hexdigest(), datetime.now(timezone.utc).isoformat()))
        current_policy = load_test_policy()
        require_test_ready(current_policy, recipient, sender)
        if current_policy != policy:
            raise ValueError("CONTROLLED_TEST_POLICY_CHANGED")
        msg = _build_email(recipient, item["subject"], item["body_text"], item["body_html"])
        from v6_bestseller_evidence import attach_verified_cid
        msg = attach_verified_cid(msg, item['body_html'], policy.get('tiktok_ranking_evidence'))
        server = _create_connection()
        try:
            rejected = server.sendmail(sender, [recipient], msg.as_string())
            if rejected:
                raise RuntimeError("CONTROLLED_TEST_SMTP_RECIPIENT_REJECTED")
        finally:
            try:
                server.quit()
            except Exception:
                pass
        accepted_at = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(AUDIT_PATH)) as conn, conn:
            conn.execute("UPDATE internal_tests SET smtp_accepted_at=?,message_id=? WHERE test_run_id=? AND template_id=?",
                (accepted_at, msg['Message-ID'], policy["test_run_id"], item["template_id"]))
        results.append({"template_id": item["template_id"], "message_id": msg['Message-ID'],
            "smtp_accepted_at": accepted_at, "smtp_accepted": True, "mailbox_validation": "UNKNOWN"})
    return {"status": "SMTP_ACCEPTED_AWAITING_MAILBOX_VALIDATION", "results": results}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    print(json.dumps(send_internal_tests(send=args.send), ensure_ascii=False, indent=2))
