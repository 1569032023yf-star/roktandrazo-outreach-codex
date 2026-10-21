"""门禁回归 / Gate regression: byte pinning is never a directory ignore."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.lead_insert_scan import unauthorized_lead_inserts


class LeadInsertScanTests(unittest.TestCase):
    def test_exact_local_artifact_accepted_but_changed_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rel = 'autonomy/runtime/dual_source_import/collector.py'
            file = root / rel
            file.parent.mkdir(parents=True)
            raw = b"sql = 'INSERT INTO leads VALUES (1)'\n"
            file.write_bytes(raw)
            with patch('tests.lead_insert_scan.LOCAL_ARTIFACTS', {rel: hashlib.sha256(raw).hexdigest()}):
                self.assertEqual(unauthorized_lead_inserts(root), [])
                file.write_bytes(raw + b"# changed\n")
                self.assertEqual(unauthorized_lead_inserts(root), [str(Path(rel))])

    def test_malicious_insert_in_runtime_and_root_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for rel in ('evil.py', 'autonomy/runtime/new/evil.py'):
                file = root / rel
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("sql = 'INSERT OR REPLACE INTO leads VALUES (1)'", encoding='utf-8')
            self.assertEqual(len(unauthorized_lead_inserts(root)), 2)

    def test_existing_approval_gate_remains_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'guarded.py').write_text(
                "require_legacy_lead_insert_approval(conn)\nsql = 'INSERT INTO leads VALUES (1)'",
                encoding='utf-8')
            self.assertEqual(unauthorized_lead_inserts(root), [])
