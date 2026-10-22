"""AST-only candidate trace checks / 仅 AST 加载候选轨迹，不加载环境或生产入口。"""
import ast
import difflib
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'patches/production/phase4a8v/baseline/bd_orchestrator.py'
CANDIDATE = ROOT / 'patches/production/phase4a8v/candidate/bd_orchestrator.py'


def load_functions(path, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {'stage_inventory', '_inventory_trace_event'}]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<isolated-inventory>', 'exec'), namespace)
    return namespace


class Connection:
    in_transaction = False
    closed = False
    def __enter__(self):
        self.in_transaction = True
        return self
    def __exit__(self, *args):
        self.in_transaction = False
    def execute(self, *args):
        return types.SimpleNamespace(fetchone=lambda: (0,))
    def close(self):
        self.closed = True


class Harness:
    def __init__(self, path=CANDIDATE, crash=None, fail_trace=False, safe=56, lock=True, state_error=None,
                 provider_error=False):
        self.conn = Connection()
        self.writes, self.business, self.finishes = [], [], []
        self.released = 0
        self.crash, self.fail_trace = crash, fail_trace
        def update(run_id, **kwargs):
            self.assert_outside()
            value = kwargs.get('current_step', '')
            if value.startswith('{') and self.fail_trace:
                raise OSError('trace_store_failed')
            self.writes.append(value)
        def lane(name, **values):
            def perform(*args, **kwargs):
                self.business.append((name, kwargs))
                if not self.conn.in_transaction:
                    raise AssertionError('business outside owning transaction')
                if name == self.crash:
                    raise LookupError('merchant secret must not enter trace')
                return types.SimpleNamespace(**values)
            return perform
        service = types.SimpleNamespace(provider=types.SimpleNamespace(provider_name='fixture'))
        service.run_places_batch = lane('places', status='provider_timeout' if provider_error else 'query_completed',
                                       provider_errors=int(provider_error), error='fixture', results_seen=3, new_unique_places=2)
        service.run_website_resolution = lane('website', results_seen=1)
        service.run_staging_postprocess = lane('postprocess', results_seen=1)
        def linked(*args, **kwargs):
            lane('linked')(*args, **kwargs)
            return {'processed': 2}
        service.run_linked_backlog = linked
        def complete(*args, **kwargs):
            self.business.append(('completion', kwargs))
            return False
        def release(*args):
            self.released += 1
        queue = types.ModuleType('retail_city_queue')
        queue.activate_next_city = lambda *a, **k: {'id': 22, 'city': 'fixture', 'state': 'NY'}
        queue.complete_active_city_if_exhausted = complete
        queue.seed_default_queue = lambda *a: None
        discovery = types.ModuleType('discovery.discovery_service')
        discovery.DiscoveryService = lambda *a: service
        resolver = types.ModuleType('discovery.website_resolver')
        resolver.ProviderWebsiteResolver = lambda *a: object()
        self.modules = {queue.__name__: queue, discovery.__name__: discovery, resolver.__name__: resolver}
        self.ns = load_functions(path, dict(datetime=datetime, timedelta=timedelta, timezone=timezone, os=os,
            inventory_target_for_date=lambda _: 50, header=lambda *a: None, log=lambda *a: None,
            set_execution_mode=lambda *a: None, update_job_run=update,
            acquire_run_lock=lambda *a: lock, release_run_lock=release,
            finish_job_run=lambda *a, **k: self.finishes.append((a, k)),
            _resolve_active_discovery_state=lambda: ('NY', state_error), get_db=lambda: self.conn,
            _count_safe_ready_pool=lambda _: safe, _count_broad_ready_pool=lambda: safe,
            get_sendable_leads=lambda **k: []))
    def assert_outside(self):
        if self.conn.in_transaction:
            raise AssertionError('trace write while business transaction owns connection')
    def run(self, dry=False):
        with patch.dict('sys.modules', self.modules), patch.dict(os.environ, {}, clear=True):
            return self.ns['stage_inventory']('inventory:fixture', '2026-10-22', dry)
    @property
    def events(self):
        writes = [json.loads(value) for value in self.writes if value.startswith('{')]
        return writes[-1]['events'] if writes else []


class StageTraceTests(unittest.TestCase):
    def test_transport_patch_matches_exact_fixture_bytes_without_crlf(self):
        expected = b''.join(difflib.diff_bytes(
            difflib.unified_diff, BASELINE.read_bytes().splitlines(keepends=True),
            CANDIDATE.read_bytes().splitlines(keepends=True),
            fromfile=b'a/bd_orchestrator.py', tofile=b'b/bd_orchestrator.py'))
        actual = (CANDIDATE.parent.parent / 'change.patch').read_bytes()
        self.assertEqual(actual, expected)
        self.assertNotIn(b'\r\n', actual)

    def test_exact_baseline_and_only_two_functions_changed(self):
        self.assertEqual(hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
                         'e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903')
        old = ast.parse(BASELINE.read_text(encoding='utf-8'))
        new = ast.parse(CANDIDATE.read_text(encoding='utf-8'))
        def rest(tree):
            return ast.dump(ast.Module(body=[n for n in tree.body if not isinstance(n, ast.FunctionDef)
                          or n.name not in {'stage_inventory', '_inventory_trace_event'}], type_ignores=[]))
        self.assertEqual(rest(old), rest(new))

    def test_order_counts_aware_utc_and_no_identity(self):
        h = Harness()
        self.assertTrue(h.run())
        self.assertEqual([(e['phase'], e['outcome']) for e in h.events],
                         [(p, o) for p in ('inventory', 'state', 'city', 'places', 'website', 'postprocess', 'linked', 'completion')
                          for o in (('enter',) if p == 'inventory' else ('enter', 'complete'))] + [('inventory', 'complete')])
        self.assertEqual([e['seq'] for e in h.events], list(range(1, 17)))
        for e in h.events:
            self.assertEqual(datetime.fromisoformat(e['at']).utcoffset(), timedelta(0))
            self.assertLessEqual(set(e), {'seq', 'phase', 'outcome', 'at', 'city_id', 'count'})
        self.assertNotIn('fixture', json.dumps(h.events))
        self.assertEqual(h.released, 1)
        self.assertTrue(h.conn.closed)

    def test_midstage_exception_retains_enter_without_false_completion(self):
        h = Harness(crash='website')
        with self.assertRaisesRegex(LookupError, 'merchant secret'):
            h.run()
        self.assertEqual(h.events[-2]['phase'], 'website')
        self.assertEqual(h.events[-2]['outcome'], 'enter')
        self.assertEqual(h.events[-1]['outcome'], 'failed')
        self.assertNotIn('secret', json.dumps(h.events))
        self.assertEqual(h.released, 1)

    def test_trace_failure_is_fail_closed_and_releases_lock(self):
        h = Harness(fail_trace=True)
        with self.assertRaisesRegex(OSError, 'trace_store_failed'):
            h.run()
        self.assertEqual(h.business, [])
        self.assertEqual(h.released, 1)
        self.assertEqual(h.finishes[-1][0][1], 'stopped')

    def test_secondary_trace_failure_does_not_mask_business_error(self):
        h = Harness(crash='website')
        original = h.ns['update_job_run']
        def update(run_id, **kwargs):
            if '"outcome":"failed"' in kwargs.get('current_step', ''):
                raise OSError('secondary_trace_failure')
            original(run_id, **kwargs)
        h.ns['update_job_run'] = update
        with self.assertRaisesRegex(LookupError, 'merchant secret'):
            h.run()
        self.assertEqual(h.events[-1]['phase'], 'website')
        self.assertEqual(h.events[-1]['outcome'], 'enter')
        self.assertEqual(h.released, 1)

    def test_final_trace_failure_never_first_finishes_job_completed(self):
        h = Harness()
        original = h.ns['update_job_run']
        def update(run_id, **kwargs):
            value = kwargs.get('current_step', '')
            if value.startswith('{'):
                last = json.loads(value)['events'][-1]
                if last['phase'] == 'inventory' and last['outcome'] == 'complete':
                    raise OSError('final_trace_store_failed')
            original(run_id, **kwargs)
        h.ns['update_job_run'] = update
        with self.assertRaisesRegex(OSError, 'final_trace_store_failed'):
            h.run()
        self.assertEqual([call[0][1] for call in h.finishes], ['stopped'])
        self.assertEqual(h.events[-1]['outcome'], 'failed')
        self.assertEqual(h.released, 1)

    def test_baseline_business_calls_and_outcome_preserved(self):
        for safe in (49, 56):
            old, new = Harness(BASELINE, safe=safe), Harness(safe=safe)
            self.assertEqual(old.run(), new.run())
            self.assertEqual(old.business, new.business)
            self.assertEqual(old.finishes, new.finishes)

    def test_provider_failure_preserves_baseline_stop(self):
        old, new = Harness(BASELINE, provider_error=True), Harness(provider_error=True)
        self.assertEqual(old.run(), new.run())
        self.assertEqual(old.business, new.business)
        self.assertEqual(old.finishes, new.finishes)
        self.assertEqual(new.events[-1]['outcome'], 'failed')

    def test_lock_conflict_and_dry_run_preserve_no_trace_no_provider(self):
        for kwargs, dry in (({'lock': False}, False), ({}, True)):
            old, new = Harness(BASELINE, **kwargs), Harness(**kwargs)
            self.assertEqual(old.run(dry), new.run(dry))
            self.assertEqual(old.business, new.business)
            self.assertEqual(new.events, [])

    def test_state_failure_records_failure_without_provider(self):
        h = Harness(state_error='ACTIVE_STATE_NOT_SET')
        self.assertFalse(h.run())
        self.assertEqual(h.events[-1]['outcome'], 'failed')
        self.assertEqual(h.business, [])
        self.assertEqual(h.released, 1)

    def test_helper_rejects_pii_values_transaction_and_limits(self):
        h = Harness()
        record = h.ns['_inventory_trace_event']
        for kwargs in ({'city_id': 'merchant@example.test'}, {'count': True}, {'count': -1}):
            with self.assertRaises(ValueError):
                record('fixture', [], 'website', 'enter', **kwargs)
        with self.assertRaises(ValueError):
            record('fixture', [], 'merchant@example.test', 'enter')
        events = []
        for _ in range(20):
            record('fixture', events, 'places', 'enter')
        self.assertLess(len(h.writes[-1].encode()), 16384)
        with self.assertRaises(ValueError):
            record('fixture', events, 'places', 'enter')
        h.conn.in_transaction = True
        with self.assertRaises(RuntimeError):
            record('fixture', [], 'places', 'enter', conn=h.conn)
        h.conn.in_transaction = False
        invalid = [{'seq': 1, 'phase': 'places', 'outcome': 'enter', 'at': datetime.now(timezone.utc).isoformat(), 'email': 'secret'}]
        with self.assertRaises(ValueError):
            record('fixture', invalid, 'places', 'complete')
        for stamp in ('2026-10-22T19:00:00', '2026-10-22T19:00:00+08:00'):
            invalid = [{'seq': 1, 'phase': 'places', 'outcome': 'enter', 'at': stamp}]
            with self.assertRaises(ValueError):
                record('fixture', invalid, 'places', 'complete')

    def test_sqlite_text_stores_full_trace_without_schema_change(self):
        h = Harness()
        h.run()
        conn = sqlite3.connect(':memory:')
        try:
            conn.execute('CREATE TABLE job_runs (run_id TEXT PRIMARY KEY, current_step TEXT)')
            conn.execute('INSERT INTO job_runs VALUES (?,?)', ('fixture', h.writes[-1]))
            self.assertEqual(conn.execute('SELECT current_step FROM job_runs').fetchone()[0], h.writes[-1])
        finally:
            conn.close()

    def test_real_sqlite_owner_rejects_in_transaction_and_writes_after_commit(self):
        h = Harness()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'offline_fixture.sqlite'
            owner = sqlite3.connect(path)
            try:
                owner.execute('CREATE TABLE job_runs (run_id TEXT PRIMARY KEY, current_step TEXT)')
                owner.execute('INSERT INTO job_runs VALUES (?,?)', ('fixture', 'starting'))
                owner.commit()
                def persist(run_id, **kwargs):
                    writer = sqlite3.connect(path, timeout=0)
                    try:
                        writer.execute('UPDATE job_runs SET current_step=? WHERE run_id=?',
                                       (kwargs['current_step'], run_id))
                        writer.commit()
                    finally:
                        writer.close()
                h.ns['update_job_run'] = persist
                events = []
                owner.execute('BEGIN IMMEDIATE')
                with self.assertRaisesRegex(RuntimeError, 'inside_transaction'):
                    h.ns['_inventory_trace_event']('fixture', events, 'places', 'enter', conn=owner)
                self.assertEqual(events, [])
                owner.commit()
                h.ns['_inventory_trace_event']('fixture', events, 'places', 'enter', conn=owner)
                self.assertEqual(len(json.loads(owner.execute('SELECT current_step FROM job_runs').fetchone()[0])['events']), 1)
            finally:
                owner.close()


if __name__ == '__main__':
    unittest.main()
