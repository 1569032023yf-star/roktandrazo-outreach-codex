import io
import json
import unittest
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch
from tools import run_comparable_suite
from tools.run_comparable_suite import ProgressResult


class ProgressTests(unittest.TestCase):
    def test_interrupted_discovery_cannot_leave_old_success(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            (dest / 'result.json').write_text('{"run": 999}', encoding='utf-8')
            with patch.object(sys, 'argv', ['runner', directory]), \
                    patch.object(sys, 'path', list(sys.path)), \
                    patch.object(unittest.defaultTestLoader, 'discover', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    run_comparable_suite.main()
            self.assertFalse((dest / 'result.json').exists())
            self.assertEqual((dest / 'progress.jsonl').read_text(), '')

    def test_completed_ids_are_flushed_without_tracebacks(self):
        class Journal(io.StringIO):
            flushes = 0
            def flush(self):
                self.flushes += 1
                super().flush()
        class Fixture(unittest.TestCase):
            def test_pass(self):
                pass
            def test_fail(self):
                self.fail('synthetic private detail')
        journal = Journal()
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=
            lambda *a, **kw: ProgressResult(*a, journal=journal, **kw)).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(Fixture))
        rows = [json.loads(s) for s in journal.getvalue().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(journal.flushes, 2)
        self.assertEqual([r['run'] for r in rows], [1, 2])
        self.assertEqual(len(result.failures), 1)
        self.assertNotIn('synthetic private detail', journal.getvalue())


if __name__ == '__main__':
    unittest.main()
