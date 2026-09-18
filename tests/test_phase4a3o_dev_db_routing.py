from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import development_safety as safety


class Phase4A3ODevDatabaseRoutingTests(unittest.TestCase):
    def _effective_path_after_env_loader_and_bd_db(self, path: Path) -> str:
        env = dict(os.environ)
        env["WORKBUDDY_BD_DB_PATH"] = str(path)
        env["PYTHONPATH"] = str(safety.ROOT)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", "import env_loader, bd_db; print(bd_db.DB_PATH)"],
            cwd=safety.ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return result.stdout.strip()

    def test_explicit_development_copy_is_preserved_after_env_loader(self):
        target = safety.ROOT / "_audit_quarantine" / "phase4a3o_test" / "copy.db"
        self.assertEqual(
            self._effective_path_after_env_loader_and_bd_db(target),
            str(target.resolve()),
        )

    def test_explicit_temp_copy_is_preserved_after_env_loader(self):
        target = Path(tempfile.gettempdir()) / "phase4a3o_test" / "copy.db"
        self.assertEqual(
            self._effective_path_after_env_loader_and_bd_db(target),
            str(target.resolve()),
        )

    def test_production_and_unsafe_external_paths_are_blocked(self):
        with self.assertRaises(safety.DevelopmentSafetyError):
            safety._select_safe_database_path(safety.PRODUCTION_ROOT / "data" / "bd_leads.db")
        with self.assertRaises(safety.DevelopmentSafetyError):
            safety._select_safe_database_path(Path(r"C:\outside-development\copy.db"))

    def test_default_remains_development_runtime_database(self):
        self.assertEqual(
            safety._select_safe_database_path(None),
            str((safety.ROOT / "data" / "bd_leads_dev_runtime.db").resolve()),
        )


if __name__ == "__main__":
    unittest.main()
