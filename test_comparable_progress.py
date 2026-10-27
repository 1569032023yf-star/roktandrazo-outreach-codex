import io
import json
import unittest
from tools.run_comparable_suite import ProgressResult


class ProgressTests(unittest.TestCase):
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
