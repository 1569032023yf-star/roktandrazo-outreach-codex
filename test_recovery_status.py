"""Recovery status from actual SQLite bytes; no production paths or requests."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from autonomy.cancellation_recovery import SCHEMA, HANDOFF_SCHEMA, PROTOCOL
from autonomy.recovery_status import inspect_recovery_status


class RecoveryStatusTests(unittest.TestCase):
    def image(self, state='PREPARED', version=1, binding=None, extra=False, wal=False, binding_raw=None):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'isolated.sqlite'
            with closing(sqlite3.connect(path)) as db:
                db.execute(SCHEMA); db.execute(HANDOFF_SCHEMA)
                db.execute('PRAGMA user_version='+str(version))
                b = binding if binding is not None else dict(binding_hash='b'*64, receipts_hash='c'*64, recovery_id='d'*64, protocol=PROTOCOL)
                db.execute('INSERT INTO recoveries VALUES (?,?,?)', ('a'*64, json.dumps(b) if binding_raw is None else binding_raw, state))
                if extra: db.execute('CREATE TABLE unexpected (x)')
                db.commit()
                if wal: db.execute('PRAGMA journal_mode=WAL').fetchone()
            raw = path.read_bytes()
            return raw

    def inspect(self, raw, identity='a'*64):
        result = inspect_recovery_status(raw, hashlib.sha256(raw).hexdigest(), identity)
        for key in ('allow_dispatch','allow_cancel_dispatch','allow_reconcile','replay_allowed','production_accepted'):
            self.assertIs(result[key], False)
        self.assertEqual(result['execution_terminal'], 'UNKNOWN')
        self.assertEqual(result['lock_closed'], 'UNKNOWN')
        self.assertEqual(result['source_authorized'], 'UNKNOWN')
        return result

    def test_prepared_completed_and_absence_are_distinct_without_authority(self):
        for state in ('PREPARED','COMPLETED'):
            raw=self.image(state);before=hashlib.sha256(raw).hexdigest()
            result=self.inspect(raw)
            self.assertTrue(result['accepted']);self.assertEqual(result['journal_phase'],state)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),before)
            missing=self.inspect(raw,'e'*64)
            self.assertTrue(missing['accepted']);self.assertEqual(missing['journal_phase'],'NOT_RECORDED')

    def test_unknown_schema_and_record_shape_fail_closed(self):
        for raw in (self.image(version=2),self.image(extra=True),self.image(binding={'protocol':PROTOCOL}),
                    self.image(binding=dict(binding_hash=True,receipts_hash='c'*64,recovery_id='d'*64,protocol=PROTOCOL))):
            self.assertFalse(self.inspect(raw)['accepted'])

    def test_corrupt_wal_truncated_or_trailing_images_rejected(self):
        raw=self.image()
        for invalid in (b'x'*100,raw[:-1],raw+b'trailing',self.image(wal=True)):
            self.assertFalse(self.inspect(invalid)['accepted'])

    def test_hash_context_and_types_rejected_without_database_open(self):
        raw=self.image()
        for snapshot,sha,identity in ((raw,'0'*64,'a'*64),(raw,True,'a'*64),(raw,hashlib.sha256(raw).hexdigest(),"' OR 1=1"),
                                     (bytearray(raw),'0'*64,'a'*64),(b'', '0'*64,'a'*64)):
            self.assertFalse(inspect_recovery_status(snapshot,sha,identity)['accepted'])

    def test_binding_parse_is_bounded_and_never_echoes_invalid_data(self):
        for value in ('['*2000+'0'+']'*2000, 'secret-invalid-json', b'not-text', '{"protocol":"'+'x'*1100+'"}'):
            result=self.inspect(self.image(binding_raw=value))
            self.assertFalse(result['accepted'])
            self.assertNotIn('secret-invalid-json', str(result))

    def test_time_limit_applies_to_absent_and_present_records(self):
        from unittest.mock import patch
        raw=self.image()
        for identity in ('a'*64,'e'*64):
            with patch('autonomy.recovery_status.time.monotonic', side_effect=[0,3]):
                result=self.inspect(raw,identity)
            self.assertFalse(result['accepted'])
            self.assertEqual(result['reason'],'INSPECTION_BUDGET_EXCEEDED')

    def test_actual_partial_recovery_then_completed_snapshot_remains_observation(self):
        import test_cancellation_cost as fixtures
        from test_cancellation_recovery import prepare, authorization
        from autonomy.cancellation_recovery import recover_cancellation
        from autonomy.lock_recovery import exclusive_lock
        f=fixtures.CancellationCostTests();f.setUp();self.addCleanup(f.doCleanups)
        c=f.case;path=c.root/'status-recovery.sqlite'
        with exclusive_lock(c.runtime):
            data=prepare(f);identity=data[4]['cancel_identity']
            def fail(phase):
                if phase=='after_prepared':raise RuntimeError('isolated fault')
            result=recover_cancellation(c.adapter,authorization(c,data,path),*data[:4],recovery_path=path,fault=fail)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            before=path.read_bytes()
            self.assertEqual(self.inspect(before,identity)['journal_phase'],'PREPARED')
            self.assertEqual(path.read_bytes(),before)
            result=recover_cancellation(c.adapter,authorization(c,data,path),*data[:4],recovery_path=path)
            self.assertEqual(result['outcome'],'COMPLETED')
            after=path.read_bytes()
            self.assertEqual(self.inspect(after,identity)['journal_phase'],'COMPLETED')
            self.assertEqual(path.read_bytes(),after)
            self.assertEqual(c.backend.calls,1)


if __name__=='__main__':unittest.main()
