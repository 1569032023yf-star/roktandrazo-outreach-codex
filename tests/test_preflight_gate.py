#!/usr/bin/env python3
"""tests/test_preflight_gate.py — P0 preflight_gate 单元测试。

用内存 sqlite 造数据，unittest.mock 替换 Worker MX 网络调用（不碰真实网络）。
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import preflight_gate as g

ASIA_SH = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=ASIA_SH)
RET = "retail_distributor_v5_locked"


def iso(dt):
    return dt.isoformat()


SCHEMA = """
CREATE TABLE leads (
  id INTEGER PRIMARY KEY, store_name TEXT, store_type TEXT, email TEXT,
  status TEXT, organization_key TEXT, template_override TEXT
);
CREATE TABLE final_send_plan (
  id INTEGER PRIMARY KEY, plan_id TEXT, lead_id INTEGER, recipient_email TEXT,
  company_name TEXT, template_id TEXT, message_type TEXT, outreach_batch_date TEXT,
  planned_sequence INTEGER, subject TEXT, body_text TEXT, body_html TEXT,
  status TEXT, created_at TEXT
);
CREATE TABLE send_log (
  id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, status TEXT, sent_at TEXT
);
CREATE TABLE suppression_list (id INTEGER PRIMARY KEY, email TEXT, reason TEXT);
CREATE TABLE bounce_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, bounce_type TEXT, domain TEXT);
CREATE TABLE reply_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, reply_type TEXT);
CREATE TABLE send_authorizations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, authorization_id TEXT, plan_id TEXT,
  outreach_batch_date TEXT, plan_entries_hash TEXT, approved_entry_count INTEGER,
  database_sha256 TEXT, preflight_status TEXT, approved_at TEXT, expires_at TEXT,
  approved_by TEXT, status TEXT, created_at TEXT
);
CREATE TABLE send_authorization_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT, authorization_id TEXT, plan_entry_id INTEGER,
  lead_id INTEGER, recipient_email TEXT, entry_hash TEXT, status TEXT
);
CREATE TABLE system_config (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
"""


_OPEN_CONNS = []


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _OPEN_CONNS.append(conn)
    return conn


def add_lead(conn, lid=1, email="a@example.com", store_type="toy_store",
             store_name="Toy A", org_key="org:a", status="sendable"):
    conn.execute(
        "INSERT INTO leads (id, store_name, store_type, email, status, organization_key) "
        "VALUES (?,?,?,?,?,?)",
        (lid, store_name, store_type, email, status, org_key),
    )
    conn.commit()


def add_plan(conn, lid=1, email="a@example.com", batch="B1", template=None,
             seq=1, status="planned", body_text="Hi there, this is a clean body."):
    conn.execute(
        "INSERT INTO final_send_plan (plan_id, lead_id, recipient_email, company_name, "
        "template_id, message_type, outreach_batch_date, planned_sequence, subject, "
        "body_text, body_html, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"{batch}_{seq:04d}", lid, email, "Company", template or RET, "new_outreach",
         batch, seq, "Premium puzzles for Test", body_text, "<p>clean</p>", status,
         iso(NOW)),
    )
    conn.commit()


def add_auth(conn, batch="B1", entries=None, status="approved",
             preflight_status="passed", expires_at=None, auth_id=None):
    auth_id = auth_id or f"auth_{batch}"
    expires = expires_at or iso(NOW + timedelta(hours=1))
    conn.execute(
        "INSERT INTO send_authorizations (authorization_id, plan_id, outreach_batch_date, "
        "plan_entries_hash, approved_entry_count, database_sha256, preflight_status, "
        "approved_at, expires_at, approved_by, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (auth_id, batch, batch, "h", len(entries or []), "db", preflight_status,
         iso(NOW), expires, "system", status, iso(NOW)),
    )
    for e in (entries or []):
        conn.execute(
            "INSERT INTO send_authorization_entries (authorization_id, plan_entry_id, "
            "lead_id, recipient_email, entry_hash, status) VALUES (?,?,?,?,?,?)",
            (auth_id, e["lead_id"], e["lead_id"], e["email"], "eh", "pending"),
        )
    conn.commit()


def set_mx_cache(conn, domain, status, checked_at):
    conn.execute(
        "INSERT INTO system_config (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (f"mx_cache_{domain}", json.dumps({"status": status, "checked_at": iso(checked_at)}), iso(NOW)),
    )
    conn.commit()


def write_poller(path, heartbeat):
    Path(path).write_text(json.dumps({
        "last_heartbeat_at": heartbeat,
        "status": "alive",
    }), encoding="utf-8")


class PreflightGateTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.poller = os.path.join(self.tmp, "poller.json")
        write_poller(self.poller, iso(NOW - timedelta(minutes=1)))
        self.poller_patch = mock.patch.object(g, "OPS_POLLER_STATUS", Path(self.poller))
        self.poller_patch.start()
        self.addCleanup(self.poller_patch.stop)

    def tearDown(self):
        while _OPEN_CONNS:
            _OPEN_CONNS.pop().close()

    def _mock_mx(self, side_effect):
        """side_effect: callable(domain) -> (status, checked_at)"""
        patcher = mock.patch.object(g, "query_mx", side_effect=side_effect)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _clean_env(self):
        """基础干净环境：B1 一条 planned、MX 缓存 ok、授权 approved、无脏数据。"""
        conn = make_conn()
        add_lead(conn)
        add_plan(conn)
        set_mx_cache(conn, "example.com", "ok", NOW - timedelta(hours=1))
        add_auth(conn, entries=[{"lead_id": 1, "email": "a@example.com"}])
        return conn

    # ── query_mx 网络层 ────────────────────────────────────
    def test_query_mx_success(self):
        fake = mock.Mock()
        fake.read.return_value = json.dumps(
            {"domain": "example.com", "mx_status": "mx_pass", "checked_at": "2026-08-06T04:00:00Z"}
        ).encode()
        fake.status = 200
        with mock.patch.object(g.urllib.request, "urlopen", return_value=fake) as m:
            status, ts = g.query_mx("Example.com")
        self.assertEqual(status, "ok")
        self.assertTrue(m.called)
        # 请求体里域名应为小写
        body = json.loads(m.call_args[0][0].data)
        self.assertEqual(body["domain"], "example.com")

    def test_query_mx_network_error_returns_dns_error(self):
        with mock.patch.object(g.urllib.request, "urlopen", side_effect=OSError("boom")), \
             mock.patch.object(g, "_mx_via_dns", return_value=("dns_error", iso(NOW))):
            status, ts = g.query_mx("example.com")
        self.assertEqual(status, "dns_error")

    def test_query_mx_maps_bad_statuses(self):
        cases = {"nxdomain": "nxdomain", "no_mx_found": "null_mx",
                 "no_mail_route": "no_mail_route", "weird": "dns_error"}
        for worker, expected in cases.items():
            fake = mock.Mock()
            fake.read.return_value = json.dumps({"mx_status": worker}).encode()
            with mock.patch.object(g.urllib.request, "urlopen", return_value=fake):
                self.assertEqual(g.query_mx("x.com")[0], expected)

    # ── dns freshness ──────────────────────────────────────
    def test_dns_stale_cache_is_replaced_by_successful_live_refresh(self):
        conn = self._clean_env()
        set_mx_cache(conn, "example.com", "ok", NOW - timedelta(hours=48))  # 超龄
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertTrue(res["pass"])
        self.assertFalse(res["smtp_blocked"])
        dns = [c for c in res["checks"] if c["name"] == "dns_freshness"][0]
        self.assertEqual(dns["status"], "pass")
        self.assertIn("fresh", dns["detail"])
        self.assertIn("example.com=ok", dns["detail"])

    def test_dns_nxdomain_fails(self):
        conn = self._clean_env()
        set_mx_cache(conn, "example.com", "nxdomain", NOW - timedelta(hours=1))  # 新鲜但坏状态
        self._mock_mx(lambda d: ("nxdomain", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        dns = [c for c in res["checks"] if c["name"] == "dns_freshness"][0]
        self.assertEqual(dns["status"], "fail")
        self.assertIn("dns_nxdomain", dns["detail"])

    def test_dns_cached_ok_within_24h_passes(self):
        conn = self._clean_env()
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertTrue(res["pass"])
        dns = [c for c in res["checks"] if c["name"] == "dns_freshness"][0]
        self.assertEqual(dns["status"], "pass")

    # ── duplicate ──────────────────────────────────────────
    def test_duplicate_email_in_plan_fails(self):
        conn = make_conn()
        add_lead(conn, lid=1, email="dup@example.com")
        add_lead(conn, lid=2, email="dup@example.com", org_key="org:b")
        add_plan(conn, lid=1, email="dup@example.com", seq=1)
        add_plan(conn, lid=2, email="dup@example.com", seq=2)
        set_mx_cache(conn, "example.com", "ok", NOW - timedelta(hours=1))
        add_auth(conn, entries=[{"lead_id": 1, "email": "dup@example.com"},
                                {"lead_id": 2, "email": "dup@example.com"}])
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        dup = [c for c in res["checks"] if c["name"] == "duplicates"][0]
        self.assertEqual(dup["status"], "fail")
        self.assertIn("email_dup_in_plan", dup["detail"])

    # ── snapshot plan hash ─────────────────────────────────
    def test_snapshot_hash_mismatch_fails(self):
        conn = self._clean_env()
        snap_path = os.path.join(self.tmp, "frozen_B1.json")
        Path(snap_path).write_text(json.dumps({"plan_hash": "wronghash"}), encoding="utf-8")
        res = g.check_snapshot_plan_hash(conn, snap_path, conn.execute(
            "SELECT * FROM final_send_plan WHERE outreach_batch_date='B1' AND status='planned'"
        ).fetchall())
        self.assertEqual(res["status"], "fail")
        self.assertIn("mismatch", res["detail"])

    def test_snapshot_hash_match_passes(self):
        conn = self._clean_env()
        snap_path = os.path.join(self.tmp, "frozen_B1.json")
        rows = conn.execute(
            "SELECT * FROM final_send_plan WHERE outreach_batch_date='B1' AND status='planned'"
        ).fetchall()
        items = sorted((str(r["lead_id"]), str(r["recipient_email"]).strip().lower(), r["template_id"] or "") for r in rows)
        digest = __import__("hashlib").sha256(
            json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        Path(snap_path).write_text(json.dumps({"plan_hash": digest}), encoding="utf-8")
        res = g.check_snapshot_plan_hash(conn, snap_path, rows)
        self.assertEqual(res["status"], "pass")

    def test_snapshot_no_hash_warns(self):
        conn = self._clean_env()
        snap_path = os.path.join(self.tmp, "frozen_B1.json")
        Path(snap_path).write_text(json.dumps({"count": 1}), encoding="utf-8")
        res = g.check_snapshot_plan_hash(conn, snap_path, [])
        self.assertEqual(res["status"], "warn")

    # ── auth entries ───────────────────────────────────────
    def test_auth_entry_missing_fails(self):
        conn = make_conn()
        add_lead(conn)
        add_plan(conn)
        set_mx_cache(conn, "example.com", "ok", NOW - timedelta(hours=1))
        # 不建授权
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        auth = [c for c in res["checks"] if c["name"] == "auth_entries"][0]
        self.assertEqual(auth["status"], "fail")
        self.assertIn("no authorization", auth["detail"])

    def test_auth_expired_fails(self):
        conn = self._clean_env()
        add_auth(conn, entries=[{"lead_id": 1, "email": "a@example.com"}],
                 expires_at=iso(NOW - timedelta(minutes=1)))  # 过期
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        auth = [c for c in res["checks"] if c["name"] == "auth_entries"][0]
        self.assertIn("expired", auth["detail"])

    # ── stale objects ──────────────────────────────────────
    def test_old_planned_plan_fails(self):
        conn = self._clean_env()
        add_plan(conn, lid=1, email="a@example.com", batch="OLD_BATCH", seq=1)
        set_mx_cache(conn, "oldbatch.com", "ok", NOW - timedelta(hours=1))  # 无实际用处
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        stale = [c for c in res["checks"] if c["name"] == "stale_objects"][0]
        self.assertEqual(stale["status"], "fail")
        self.assertIn("old_planned_plan", stale["detail"])

    def test_poller_stale_fails(self):
        write_poller(self.poller, iso(NOW - timedelta(minutes=45)))
        conn = self._clean_env()
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        stale = [c for c in res["checks"] if c["name"] == "stale_objects"][0]
        self.assertIn("poller_heartbeat_stale", stale["detail"])

    # ── hygiene ────────────────────────────────────────────
    def test_suppressed_lead_fails(self):
        conn = self._clean_env()
        conn.execute("INSERT INTO suppression_list (email, reason) VALUES ('a@example.com','test')")
        conn.commit()
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        hyg = [c for c in res["checks"] if c["name"] == "hygiene"][0]
        self.assertEqual(hyg["status"], "fail")

    def test_hard_bounce_fails(self):
        conn = self._clean_env()
        conn.execute("INSERT INTO bounce_log (lead_id, email, bounce_type) VALUES (1,'a@example.com','hard')")
        conn.commit()
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        hyg = [c for c in res["checks"] if c["name"] == "hygiene"][0]
        self.assertIn("hard_bounce", hyg["detail"])

    def test_reply_fails(self):
        conn = self._clean_env()
        conn.execute("INSERT INTO reply_log (lead_id, email) VALUES (1,'a@example.com')")
        conn.commit()
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        hyg = [c for c in res["checks"] if c["name"] == "hygiene"][0]
        self.assertIn("replied", hyg["detail"])

    # ── all clean ──────────────────────────────────────────
    def test_all_clean_passes(self):
        conn = self._clean_env()
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertTrue(res["pass"])
        self.assertFalse(res["smtp_blocked"])
        self.assertEqual(res["batch_id"], "B1")
        for c in res["checks"]:
            self.assertIn(c["status"], ("pass", "warn"), f"{c['name']} -> {c['status']}")
        self.assertEqual(res["blocks"], [])

    def test_no_planned_rows_fails(self):
        conn = make_conn()
        self._mock_mx(lambda d: ("ok", iso(NOW)))
        res = g.run_preflight(conn, "B1", require_dns=True, now=NOW)
        self.assertFalse(res["pass"])
        self.assertTrue(res["smtp_blocked"])
        self.assertIn("planned_rows_present", res["blocks"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
