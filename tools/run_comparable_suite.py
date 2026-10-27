"""Same-process-startup offline suite runner; writes local diagnostic artifacts only."""
import contextlib
import json
from pathlib import Path
import sys
import unittest

class ProgressResult(unittest.TextTestResult):
    """Flush stopped IDs; interruption may leave the outcome unknown."""
    def __init__(self, *args, journal, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal

    def stopTest(self, test):
        super().stopTest(test)
        self.journal.write(json.dumps({'stopped_test': test.id(),
                                      'run': self.testsRun}) + '\n')
        self.journal.flush()

def main():
    root = Path.cwd()
    sys.path.insert(0, str(root))
    dest = Path(sys.argv[1]).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    # A previous complete result must not survive a new interrupted attempt.
    (dest / 'result.json').unlink(missing_ok=True)
    with (dest / 'raw.txt').open('w', encoding='utf-8') as output, \
            (dest / 'progress.jsonl').open('w', encoding='utf-8') as journal:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
            factory = lambda *a, **kw: ProgressResult(*a, journal=journal, **kw)
            result = unittest.TextTestRunner(stream=output, verbosity=2,
                                            resultclass=factory).run(suite)
    data = {'run': result.testsRun, 'failures': [t.id() for t, _ in result.failures],
        'errors': [t.id() for t, _ in result.errors], 'skipped': [t.id() for t, _ in result.skipped],
        'python': sys.version, 'startup': 'tools/run_comparable_suite.py; sys.path.insert(0,cwd)',
        'development_copy': (root / '.development-copy').exists()}
    (dest / 'result.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in data.items()}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
