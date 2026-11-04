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


def leaves(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from leaves(item)
        else:yield item

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
            factory = lambda *a, **kw: ProgressResult(*a, journal=journal, **kw)
            # Execute offline native admission before business-module discovery
            # installs global transport/process guards. Never uninstall guards.
            # Every native test is executed once and remains in combined totals.
            early=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_u1_runtime_content.py')
            early_ids=[t.id() for t in leaves(early)]
            runner=unittest.TextTestRunner(stream=output,verbosity=2,resultclass=factory)
            first=runner.run(early)
            suite=unittest.defaultTestLoader.discover(str(root/'tests'))
            all_tests=list(leaves(suite));all_ids=[t.id() for t in all_tests]
            if len(early_ids)!=len(set(early_ids)) or not set(early_ids)<=set(all_ids):
                raise RuntimeError('EARLY_TEST_ACCOUNTING_MISMATCH')
            remaining=unittest.TestSuite(t for t in all_tests if t.id() not in set(early_ids))
            second=runner.run(remaining)
            results=[first,second]
    data = {'run': sum(r.testsRun for r in results), 'failures': [t.id() for r in results for t, _ in r.failures],
        'errors': [t.id() for r in results for t, _ in r.errors], 'skipped': [t.id() for r in results for t, _ in r.skipped],
        'python': sys.version, 'startup': 'tools/run_comparable_suite.py; sys.path.insert(0,cwd); native admission before business discovery',
        'early_test_ids':early_ids,'discovered_test_count':len(all_tests),
        'phases':[dict(run=r.testsRun,failures=len(r.failures),errors=len(r.errors)) for r in results],
        'development_copy': (root / '.development-copy').exists()}
    (dest / 'result.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in data.items()}))
    return 0 if all(r.wasSuccessful() for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
