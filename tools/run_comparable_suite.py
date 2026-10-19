"""Same-process-startup offline suite runner; writes local diagnostic artifacts only."""
import contextlib
import json
from pathlib import Path
import sys
import unittest

root = Path.cwd()
sys.path.insert(0, str(root))
dest = Path(sys.argv[1]).resolve()
dest.mkdir(parents=True, exist_ok=True)
with (dest / 'raw.txt').open('w', encoding='utf-8') as output:
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
data = {'run': result.testsRun, 'failures': [t.id() for t, _ in result.failures],
    'errors': [t.id() for t, _ in result.errors], 'skipped': [t.id() for t, _ in result.skipped],
    'python': sys.version, 'startup': 'tools/run_comparable_suite.py; sys.path.insert(0,cwd)',
    'development_copy': (root / '.development-copy').exists()}
(dest / 'result.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in data.items()}))
