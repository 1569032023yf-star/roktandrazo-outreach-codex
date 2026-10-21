"""Explicitly load pinned files for offline validation / 显式加载固定候选离线验证。"""
import argparse
import contextlib
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUITE = ['tests.test_city_network_recovery', 'tests.test_discovery_service',
         'tests.test_phase4a1b_linked_backlog', 'tests.test_phase4a7_city_queue_advancement',
         'tests.test_phase4a8d_access_unreachable_city_liveness',
         'tests.test_phase4a8q_identity_terminal_hotfix', 'tests.test_lead_insert_scan']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy-tests', action='store_true')
    parser.add_argument('--suite', nargs='+')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    args.output.mkdir(parents=True, exist_ok=True)
    loaded = {}
    for name, rel in [('retail_city_queue', 'retail_city_queue.py'),
                      ('discovery.discovery_service', 'discovery/discovery_service.py')]:
        path = args.source / rel
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        loaded[name] = str(path.resolve())
    if args.legacy_tests:
        import tests
        for name in ('tests.test_discovery_service', 'tests.test_phase4a1b_linked_backlog', 'tests.test_city_network_recovery',
                     'tests.test_phase4a8d_access_unreachable_city_liveness'):
            rel = name.replace('.', '/') + '.py'
            source = (args.source / rel).read_bytes()
            module = types.ModuleType(name)
            module.__file__ = str(ROOT / rel)
            sys.modules[name] = module
            setattr(tests, name.rsplit('.', 1)[1], module)
            exec(compile(source, module.__file__, 'exec'), module.__dict__)
    with (args.output / 'tests.log').open('w', encoding='utf-8') as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            # Imported fixture classes are not separate tests in this suite.
            suite = unittest.TestSuite()
            for name in (args.suite or SUITE):
                module = importlib.import_module(name)
                for value in vars(module).values():
                    if isinstance(value, type) and issubclass(value, unittest.TestCase) and value.__module__ == name:
                        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(value))
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {'summary_zh': '固定源码离线回归，非生产运行证据',
              'summary_en': 'Pinned-source offline regression, not production execution evidence',
              'ran_at': datetime.now(timezone.utc).isoformat(), 'loaded_files': loaded,
              'total': result.testsRun, 'failed': len(result.failures) + len(result.errors),
              'failures': [test.id() for test, _ in result.failures],
              'errors': [test.id() for test, _ in result.errors],
              'exit_code': 0 if result.wasSuccessful() else 1}
    (args.output / 'tests.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return report['exit_code']


if __name__ == '__main__':
    sys.exit(main())
