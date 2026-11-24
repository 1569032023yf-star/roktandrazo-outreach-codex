"""Checks for the new-file sections in the fixed internal QA candidate."""
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "publisher_channel"))
import multifile
import executor
import json


class CandidatePatchSections(unittest.TestCase):
    def test_candidate_new_file_sections(self):
        patch = (ROOT / "patches/production/phase5a/qa-candidate-e6b4999/internal-qa.patch").read_bytes()
        self.assertEqual(hashlib.sha256(patch).hexdigest(),
                         "0dd8f4207d876a53c6adb282216fefa8a73eefca904f2ab18088851979560c86")
        sections = multifile.parse_sections(patch)
        self.assertEqual({s["path"] for s in sections},
                         {"v6_outreach.py", "v6_bestseller_evidence.py", "controlled_v6_test.py"})
        self.assertTrue(all(s["before_absent"] for s in sections))
        request = json.loads((ROOT / "patches/production/phase5a/qa-candidate-e6b4999/internal-qa-request.json").read_text(encoding="utf-8"))
        expected = {f["file"]: f["after_sha256"] for f in request["files"]}
        for section in sections:
            with self.subTest(path=section["path"]):
                candidate = executor.apply_unified(b"", section["section"], section["path"], expected_hunks=section["hunk_count"])
                self.assertEqual(hashlib.sha256(candidate).hexdigest(), expected[section["path"]])
                self.assertEqual(executor.apply_unified(candidate, section["section"], section["path"], reverse=True, expected_hunks=section["hunk_count"]), b"")
                with self.assertRaises(executor.GateError):
                    executor.apply_unified(b"unexpected", section["section"], section["path"], expected_hunks=section["hunk_count"])

    def test_malformed_absent_header_fails_closed(self):
        with self.assertRaises(multifile.PatchError):
            multifile.parse_sections(b"--- /dev/null\n+++ /dev/null\n@@ -0,0 +1 @@\n+x\n")


if __name__ == "__main__":
    unittest.main()
