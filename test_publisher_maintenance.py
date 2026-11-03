"""Original publisher admission, isolated SQLite only; no channel config load."""
import ast
from contextlib import closing, ExitStack
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from autonomy import inventory_maintenance as maintenance

SOURCE = Path(__file__).parent/'publisher_channel/executor.py'
spec = importlib.util.spec_from_file_location('isolated_publisher_executor', SOURCE)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublisherMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='u1-publisher-maintenance-')
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name)/'authority.db'
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)')
            conn.commit()
        self.cfg = {'production': {'db_path': str(self.db)},
                    'lock': {'key_prefix': maintenance.PREFIX, 'stale_after_seconds': -1}}
        self.binding = dict(inventory_id='1784775229336', operation_id='a'*64,
                            source_commit='b'*40, manifest_sha256='c'*64, lease_nonce='d'*64)

    def test_marker_blocks_apply_and_rollback_holders_across_dates(self):
        with closing(sqlite3.connect(self.db)) as conn:
            maintenance.acquire(conn, self.binding)
            for day in ('2026-11-03', '2026-11-04'):
                with patch.object(publisher, 'business_date_shanghai', return_value=day):
                    for holder in ('deploy:op-test', 'rollback:op-test'):
                        ok, result = publisher.inventory_acquire(self.cfg, holder)
                        self.assertFalse(ok)
                        self.assertEqual(result['reason'], 'STOP_AND_PRESERVE_MAINTENANCE_HELD')
            self.assertEqual(conn.execute('SELECT count(*) FROM system_config WHERE key LIKE ?',
                                         (maintenance.PREFIX+'%',)).fetchone()[0], 0)
            maintenance.assert_held(conn, self.binding)

    def test_released_marker_allows_original_admission_but_operation_cannot_replay(self):
        with closing(sqlite3.connect(self.db)) as conn:
            maintenance.acquire(conn, self.binding)
            maintenance.release_verified(conn, self.binding, final_verified=True)
            self.assertTrue(publisher.inventory_acquire(self.cfg, 'deploy:op-test')[0])
            with self.assertRaisesRegex(ValueError, 'REPLAY'):
                maintenance.acquire(conn, self.binding)

    def test_publisher_holder_blocks_maintenance_even_with_expired_timestamp(self):
        self.assertTrue(publisher.inventory_acquire(self.cfg, 'deploy:op-test')[0])
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('UPDATE system_config SET value=? WHERE key LIKE ?',
                         ('2000-01-01 00:00:00', maintenance.PREFIX+'%_acquired_at'))
            conn.commit()
            with self.assertRaisesRegex(ValueError, 'NOT_QUIESCENT'):
                maintenance.acquire(conn, self.binding)
            self.assertFalse(maintenance.blocked(conn))

    def test_malformed_null_and_empty_markers_fail_closed(self):
        for value in ('malformed', '', None):
            with self.subTest(value=value), closing(sqlite3.connect(self.db)) as conn:
                conn.execute('INSERT OR REPLACE INTO system_config VALUES(?,?,NULL)',
                             (maintenance.KEY, value))
                conn.commit()
                self.assertFalse(publisher.inventory_acquire(self.cfg, 'deploy:op-test')[0])

    def test_racing_maintenance_and_publisher_have_exactly_one_winner(self):
        barrier = threading.Barrier(2)
        results = []
        def maintain():
            with closing(sqlite3.connect(self.db)) as conn:
                barrier.wait()
                try:
                    maintenance.acquire(conn, self.binding)
                    results.append(('maintenance', True))
                except ValueError:
                    results.append(('maintenance', False))
        def publish():
            barrier.wait()
            results.append(('publisher', publisher.inventory_acquire(self.cfg, 'deploy:op-race')[0]))
        a = threading.Thread(target=maintain); b = threading.Thread(target=publish)
        a.start(); b.start(); a.join(10); b.join(10)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(ok for _, ok in results), 1)

    def test_missing_authority_table_raises_without_publisher_admission(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('DROP TABLE system_config'); conn.commit()
        with self.assertRaises(sqlite3.OperationalError):
            publisher.inventory_acquire(self.cfg, 'deploy:op-test')

    def test_all_four_original_mutating_paths_use_shared_admission_before_replace(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        for name in ('op_apply', 'op_apply_multi', 'op_rollback', 'op_rollback_multi'):
            fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name)
            calls = [x for x in ast.walk(fn) if isinstance(x, ast.Call)]
            admission = [x.lineno for x in calls if isinstance(x.func, ast.Name)
                         and x.func.id == 'inventory_acquire']
            swaps = [x.lineno for x in calls if isinstance(x.func, ast.Attribute)
                     and x.func.attr == 'replace']
            self.assertEqual(len(admission), 1, name)
            self.assertTrue(swaps, name)
            self.assertLess(admission[0], min(swaps), name)

    def test_actual_single_multi_apply_and_rollback_refuse_effects_after_green_preflight(self):
        # Keep actual operation bodies and actual DB admission. Doubles isolate
        # seal/config and earlier preflight only; no production config is loaded.
        target = Path(self.tmp.name)/'target.py'; target.write_bytes(b'after')
        backup = Path(self.tmp.name)/'before.bak'; backup.write_bytes(b'before')
        before = publisher.sha256_hex(b'before'); after = publisher.sha256_hex(b'after')
        rel = dict(before_sha256=before, after_sha256=after, target_relative_path='target.py', hunk_count=1)
        item = dict(path='target.py', before_sha256=before, after_sha256=after)
        rec = dict(state='applied', release_id='test', backup=str(backup),
                   files=[dict(path='target.py', target=str(target), backup=str(backup))])
        cfg = dict(self.cfg, channel_id='isolated', _test_mode=True,
                   _paths={'backups': str(Path(self.tmp.name)/'backups')})
        with closing(sqlite3.connect(self.db)) as conn:
            maintenance.acquire(conn, self.binding)
        with ExitStack() as stack:
            for name, result in [('_assert_seal', {}), ('get_release', rel),
                                 ('live_gates', {}), ('live_gates_multi', {}),
                                 ('gates_summary', {'all_pass': True}),
                                 ('resolve_target', target), ('read_patch', b'unused'),
                                 ('resolve_targets', [(item, target)]), ('release_files', [item]),
                                 ('load_operations', {'operations': {'op-test': rec}})]:
                stack.enter_context(patch.object(publisher, name, return_value=result))
            for name in ('_record', 'audit', 'save_operations'):
                stack.enter_context(patch.object(publisher, name))
            swap = stack.enter_context(patch.object(publisher.os, 'replace', side_effect=AssertionError('NO_SWAP_ALLOWED')))
            dacl = stack.enter_context(patch.object(publisher, 'copy_dacl', side_effect=AssertionError('NO_ACL_ALLOWED')))
            for call in (lambda: publisher.op_apply(cfg, 'test', 'isolated', True),
                         lambda: publisher.op_apply_multi(cfg, 'test', 'isolated', True),
                         lambda: publisher.op_rollback(cfg, 'op-test', 'isolated'),
                         lambda: publisher.op_rollback_multi(cfg, 'op-test', rec, 'isolated')):
                result = call()
                self.assertIn('LOCK_CONFLICT', result['verdict'])
                self.assertEqual(result['state'], 'failed')
                self.assertEqual(target.read_bytes(), b'after')
                self.assertEqual(backup.read_bytes(), b'before')
            swap.assert_not_called(); dacl.assert_not_called()
        with closing(sqlite3.connect(self.db)) as conn:
            maintenance.assert_held(conn, self.binding)


if __name__ == '__main__':
    unittest.main()
