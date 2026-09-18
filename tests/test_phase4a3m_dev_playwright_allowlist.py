from __future__ import annotations

import imaplib
import os
import smtplib
import sys
import unittest
from pathlib import Path
from unittest import mock

import bd_db  # Installs development-only SMTP/IMAP/subprocess guards.
import development_safety as safety


class Phase4A3MDevelopmentSafetyTests(unittest.TestCase):
    def setUp(self):
        self.driver_root = safety._active_playwright_driver_root()
        self.assertIsNotNone(self.driver_root, "active Python environment must provide Playwright driver")
        self.driver = self.driver_root / "node.exe"
        self.assertTrue(self.driver.is_file())

    def test_active_environment_playwright_driver_requires_controlled_web(self):
        with mock.patch.dict(os.environ, {"ROKT_DEV_CONTROLLED_WEB": "0"}, clear=False):
            self.assertFalse(safety._subprocess_is_allowed([str(self.driver), "driver.js"], safety.ROOT))
        with mock.patch.dict(os.environ, {"ROKT_DEV_CONTROLLED_WEB": "1"}, clear=False):
            self.assertTrue(safety._subprocess_is_allowed([str(self.driver), "driver.js"], safety.ROOT))

    def test_arbitrary_node_and_non_playwright_global_executable_remain_blocked(self):
        with mock.patch.dict(os.environ, {"ROKT_DEV_CONTROLLED_WEB": "1"}, clear=False):
            self.assertFalse(safety._subprocess_is_allowed([r"C:\\tools\\node.exe", "anything.js"], safety.ROOT))
            self.assertFalse(safety._subprocess_is_allowed([r"C:\\Windows\\System32\\cmd.exe", "/c", "whoami"], safety.ROOT))

    def test_smtp_imap_and_production_db_remain_fail_closed(self):
        with self.assertRaises(safety.DevelopmentSafetyError):
            smtplib.SMTP("smtp.example.test", 25)
        with self.assertRaises(safety.DevelopmentSafetyError):
            imaplib.IMAP4("imap.example.test", 143)
        with self.assertRaises(safety.DevelopmentSafetyError):
            safety.assert_safe_database_path(safety.PRODUCTION_ROOT / "data" / "bd_leads.db")

    def test_safe_python_subprocess_behavior_is_unchanged(self):
        self.assertTrue(safety._subprocess_is_allowed([sys.executable, "-c", "pass"], safety.ROOT))
        self.assertFalse(safety._subprocess_is_allowed([sys.executable, "-I", "-c", "pass"], safety.ROOT))


if __name__ == "__main__":
    unittest.main()
