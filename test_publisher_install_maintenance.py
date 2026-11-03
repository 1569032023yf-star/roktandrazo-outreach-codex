"""Publisher maintenance lifecycle with actual isolated authority transactions."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from autonomy import inventory_maintenance as authority
from publisher_channel.install_maintenance import InstallMaintenance


class PublisherInstallMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='u1-install-authority-')
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name)/'authority.db'
        self.conn = sqlite3.connect(self.db); self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)')
        self.conn.commit()
        self.binding = dict(inventory_id='1784775229336', operation_id='a'*64,
                            source_commit='b'*40, manifest_sha256='c'*64, lease_nonce='d'*64)
        self.session = InstallMaintenance(self.conn, self.binding, target_operation_id='e'*64, action='install')

    def held(self, session):
        return session.assert_held('e'*64, 'b'*40, 'c'*64, 'install')

    def proof(self, session, observed):
        self.held(session)
        return dict(context=session.context, outcome='COMMITTED', evidence_sha256='f'*64)

    def test_hold_from_install_through_independent_final_verification_and_atomic_release(self):
        calls = []
        def install(session):
            self.assertTrue(self.held(session)); calls.append('install'); return 'observed'
        def verify(session, observed):
            self.assertEqual(observed, 'observed'); calls.append('verify')
            return self.proof(session, observed)
        result = self.session.execute(install, verify)
        self.assertEqual(calls, ['install', 'verify'])
        self.assertEqual(result['outcome'], 'COMMITTED')
        self.assertFalse(authority.blocked(self.conn))
        records, _ = self.session._records()
        self.assertEqual([x['phase'] for x in records],
                         ['HELD', 'INSTALL_INTENT', 'INSTALLER_RETURNED', 'FINAL_VERIFY_INTENT', 'FINAL_VERIFIED', 'RELEASED'])
        with self.assertRaisesRegex(ValueError, 'REPLAY'):
            self.session.execute(install, verify)
        self.assertEqual(calls, ['install', 'verify'])

    def test_failure_preserves_marker_and_explicit_reconcile_never_relaunches(self):
        calls = []
        def install(session):
            calls.append('install'); raise OSError('injected partial installation')
        with self.assertRaises(OSError): self.session.execute(install, self.proof)
        authority.assert_held(self.conn, self.binding)
        self.assertEqual(self.session._records()[0][-1]['phase'], 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'REPLAY'):
            self.session.execute(install, self.proof)
        self.session.reconcile(self.proof)
        self.assertEqual(calls, ['install'])
        self.assertFalse(authority.blocked(self.conn))

    def test_actual_supervised_process_uses_session_and_keeps_maintenance_on_failure(self):
        from autonomy.process_job import run_tree
        marker = Path(self.tmp.name)/'running'
        verifies = []
        def install(session):
            live = session.process_guard()
            def invalidate_after_start():
                if marker.exists():
                    # Simulate a recorded recovery handoff: the old parent must
                    # stop even while the global exclusion remains held.
                    session._transition('UNKNOWN')
                return live()
            return run_tree([sys.executable, '-c',
                'import pathlib,time;pathlib.Path('+repr(str(marker))+').touch();time.sleep(30)'],
                timeout=5, assert_live=invalidate_after_start)
        with self.assertRaisesRegex(ValueError, 'SESSION_NOT_ACTIVE') as caught:
            self.session.execute(install, lambda *args: verifies.append(args))
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertEqual(verifies, [])
        authority.assert_held(self.conn, self.binding)
        self.assertEqual(self.session._records()[0][-1]['phase'], 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'REPLAY'):
            self.session.execute(install, self.proof)

    def test_process_guard_requires_executing_phase_and_exact_context(self):
        guard = self.session.process_guard()
        self.session.acquire()
        with self.assertRaisesRegex(ValueError, 'NOT_EXECUTING'): guard()
        self.session._transition('INSTALL_INTENT')
        self.assertTrue(guard())
        self.session.context['action'] = 'rollback'
        with self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'): guard()

    def test_wrong_binding_or_verifier_failure_never_releases(self):
        self.session.acquire()
        with self.assertRaisesRegex(ValueError, 'BINDING_MISMATCH'):
            self.session.assert_held('0'*64, 'b'*40, 'c'*64, 'install')
        with self.assertRaisesRegex(ValueError, 'BINDING_MISMATCH'):
            self.session.assert_held('e'*64, 'b'*40, 'c'*64, 'rollback')
        for proof in (True, {}, dict(context=self.session.context, outcome='UNKNOWN', evidence_sha256='f'*64)):
            with self.assertRaisesRegex(ValueError, 'FINAL_VERIFICATION'):
                self.session.reconcile(lambda *_: proof)
            authority.assert_held(self.conn, self.binding)

    def test_real_process_exit_after_install_intent_remains_held_after_restart(self):
        target = Path(self.tmp.name)/'crashed-partial'
        code = '''import json,os,sqlite3,sys
from pathlib import Path
from publisher_channel.install_maintenance import InstallMaintenance
c=sqlite3.connect(sys.argv[1]);b=json.loads(sys.argv[2])
s=InstallMaintenance(c,b,target_operation_id='e'*64,action='install')
def die(_):
    Path(sys.argv[3]).write_bytes(b'partial')
    os._exit(41)
s.execute(die,lambda *_:None)
'''
        child = subprocess.Popen([sys.executable, '-B', '-c', code, str(self.db), json.dumps(self.binding), str(target)])
        self.assertEqual(child.wait(timeout=15), 41)
        authority.assert_held(self.conn, self.binding)
        self.assertEqual(self.session._records()[0][-1]['phase'], 'INSTALL_INTENT')
        with self.assertRaisesRegex(ValueError, 'REPLAY'):
            self.session.execute(lambda _: self.fail('replayed'), self.proof)
        def stopped(session):
            self.assertEqual(child.poll(), 41)
            return dict(context=session.context, stopped=True,
                        process_identity_sha256=hashlib.sha256((str(child.pid)+code).encode()).hexdigest())
        def compensate(session):
            session.assert_held('e'*64, 'b'*40, 'c'*64, 'recover')
            self.assertEqual(target.read_bytes(), b'partial'); target.unlink()
        def verify(session, _):
            self.assertFalse(target.exists())
            return dict(context=session.context, outcome='ROLLED_BACK', evidence_sha256='f'*64)
        self.session.compensate('9'*64, compensate, verify, confirm_stopped=stopped)
        self.assertFalse(authority.blocked(self.conn))

    def test_release_commit_failure_keeps_authority_and_does_not_replay_install(self):
        conn = self.conn
        class FailedFinalCommit:
            @property
            def in_transaction(_): return conn.in_transaction
            def execute(_, *a): return conn.execute(*a)
            def rollback(_): conn.rollback()
            def commit(_):
                if conn.execute("SELECT 1 FROM system_config WHERE value LIKE '%FINAL_VERIFIED%'").fetchone():
                    raise OSError('injected release commit failure')
                conn.commit()
        self.session.conn = FailedFinalCommit()
        calls = []
        with self.assertRaises(OSError):
            self.session.execute(lambda _: calls.append('install'), self.proof)
        authority.assert_held(self.conn, self.binding)
        self.session.conn = conn
        self.session.reconcile(self.proof)
        self.assertEqual(calls, ['install'])

    def test_release_commit_succeeded_but_reply_lost_is_observed_without_replay(self):
        conn = self.conn
        class LostReply:
            @property
            def in_transaction(_): return conn.in_transaction
            def execute(_, *a): return conn.execute(*a)
            def rollback(_): conn.rollback()
            def commit(_):
                final = conn.execute("SELECT 1 FROM system_config WHERE value LIKE '%FINAL_VERIFIED%'").fetchone()
                conn.commit()
                if final: raise OSError('committed release reply lost')
        self.session.conn = LostReply()
        calls = []
        with self.assertRaises(OSError):
            self.session.execute(lambda _: calls.append('install'), self.proof)
        self.assertFalse(authority.blocked(conn))
        self.session.conn = conn
        self.assertEqual(self.session._records()[0][-1]['phase'], 'RELEASED')
        with self.assertRaisesRegex(ValueError, 'REPLAY'):
            self.session.execute(lambda _: calls.append('replayed'), self.proof)
        self.assertEqual(calls, ['install'])

    def test_explicit_rollback_has_fresh_maintenance_operation_but_same_target_journal(self):
        self.session.execute(lambda _: None, self.proof)
        binding = dict(self.binding, operation_id='1'*64, lease_nonce='2'*64)
        rollback = InstallMaintenance(self.conn, binding, target_operation_id='e'*64, action='rollback')
        def verified(session, _):
            session.assert_held('e'*64, 'b'*40, 'c'*64, 'rollback')
            return dict(context=session.context, outcome='ROLLED_BACK', evidence_sha256='3'*64)
        self.assertEqual(rollback.execute(lambda _: None, verified)['outcome'], 'ROLLED_BACK')
        self.assertFalse(authority.blocked(self.conn))

    def test_acquire_session_failure_rolls_back_marker_tombstone_and_context_together(self):
        original = self.session._append
        self.session._append = lambda *_: (_ for _ in ()).throw(OSError('HELD write failure'))
        with self.assertRaises(OSError): self.session.acquire()
        self.assertFalse(authority.blocked(self.conn))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM system_config').fetchone()[0], 0)
        self.session._append = original
        self.session.execute(lambda _: None, self.proof)

    def test_real_exit_inside_acquire_transaction_leaves_no_orphan_marker(self):
        code = '''import json,os,sqlite3,sys
from publisher_channel.install_maintenance import InstallMaintenance
c=sqlite3.connect(sys.argv[1]);s=InstallMaintenance(c,json.loads(sys.argv[2]),target_operation_id='e'*64,action='install')
s._append=lambda *_:os._exit(42)
s.acquire()
'''
        result = subprocess.run([sys.executable, '-B', '-c', code, str(self.db), json.dumps(self.binding)], timeout=15)
        self.assertEqual(result.returncode, 42)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM system_config').fetchone()[0], 0)
        self.session.execute(lambda _: None, self.proof)

    def test_explicit_partial_compensation_retains_same_authority_and_can_recover_again(self):
        target = Path(self.tmp.name)/'partial-file'
        calls = []
        def install(_):
            target.write_bytes(b'partial'); calls.append('forward'); raise OSError('install failed')
        with self.assertRaises(OSError): self.session.execute(install, self.proof)
        def stopped(session):
            return dict(context=session.context, stopped=True, process_identity_sha256='4'*64)
        def failed_recovery(session):
            session.assert_held('e'*64, 'b'*40, 'c'*64, 'recover')
            authority.assert_held(self.conn, self.binding)
            calls.append('first-recovery'); raise OSError('recovery interrupted')
        def verify(session, _):
            session.assert_held('e'*64, 'b'*40, 'c'*64, 'recover')
            self.assertFalse(target.exists())
            return dict(context=session.context, outcome='ROLLED_BACK', evidence_sha256='5'*64)
        with self.assertRaises(OSError):
            self.session.compensate('6'*64, failed_recovery, verify, confirm_stopped=stopped)
        authority.assert_held(self.conn, self.binding)
        with self.assertRaisesRegex(ValueError, 'SESSION_NOT_ACTIVE'): self.held(self.session)
        with self.assertRaisesRegex(ValueError, 'HANDED_OFF'): self.session.reconcile(self.proof)
        child = self.session.compensation_session('6'*64)
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_RECOVERY'):
            self.session.compensate('6'*64, failed_recovery, verify, confirm_stopped=stopped)
        def recover(session):
            session.assert_held('e'*64, 'b'*40, 'c'*64, 'recover')
            calls.append('second-recovery'); target.unlink()
        proof = child.compensate('7'*64, recover, verify, confirm_stopped=stopped)
        self.assertEqual(proof['outcome'], 'ROLLED_BACK')
        self.assertEqual(calls, ['forward', 'first-recovery', 'second-recovery'])
        self.assertFalse(authority.blocked(self.conn))

    def test_unverified_prior_process_cannot_start_compensation(self):
        with self.assertRaises(OSError):
            self.session.execute(lambda _: (_ for _ in ()).throw(OSError('partial')), self.proof)
        with self.assertRaisesRegex(ValueError, 'PREVIOUS_PROCESS_UNVERIFIED'):
            self.session.compensate('8'*64, lambda _: self.fail('unsafe compensation'),
                                    self.proof, confirm_stopped=lambda _: False)
        authority.assert_held(self.conn, self.binding)
        self.assertEqual(self.session._records()[0][-1]['phase'], 'UNKNOWN')

    def test_handoff_during_old_verifier_cannot_release_or_reactivate_parent(self):
        self.session.acquire()
        def stopped(session):
            return dict(context=session.context, stopped=True, process_identity_sha256='4'*64)
        def failed_recovery(_): raise OSError('child interrupted')
        def old_verifier(session, _):
            # Deterministic interleaving: old verifier read before handoff, but
            # returns its stale proof after compensation has acquired the child.
            with self.assertRaises(OSError):
                session.compensate('0'*64, failed_recovery, self.proof, confirm_stopped=stopped)
            return dict(context=session.context, outcome='COMMITTED', evidence_sha256='f'*64)
        with self.assertRaisesRegex(ValueError, 'FINAL_SESSION_CHANGED'):
            self.session.reconcile(old_verifier)
        authority.assert_held(self.conn, self.binding)
        self.assertEqual(self.session._records()[0][-1]['phase'], 'RECOVERY_ADMITTED')
        for phase in ('UNKNOWN', 'INSTALLER_RETURNED', 'FINAL_VERIFY_INTENT'):
            with self.assertRaisesRegex(ValueError, 'SESSION_TRANSITION'):
                self.session._transition(phase)
        authority.assert_held(self.conn, self.binding)

    def test_real_exit_after_handoff_before_child_intent_allows_explicit_compensation(self):
        with self.assertRaises(OSError):
            self.session.execute(lambda _: (_ for _ in ()).throw(OSError('partial')), self.proof)
        code = '''import json,os,sqlite3,sys
from publisher_channel.install_maintenance import InstallMaintenance
c=sqlite3.connect(sys.argv[1]);s=InstallMaintenance(c,json.loads(sys.argv[2]),target_operation_id='e'*64,action='install')
InstallMaintenance._execute_held=lambda *args:os._exit(43)
s.compensate('a1'*32,lambda _:None,lambda *_:None,confirm_stopped=lambda s:dict(context=s.context,stopped=True,process_identity_sha256='4'*64))
'''
        process = subprocess.Popen([sys.executable, '-B', '-c', code, str(self.db), json.dumps(self.binding)])
        self.assertEqual(process.wait(timeout=15), 43)
        child = self.session.compensation_session('a1'*32)
        self.assertEqual(child._records()[0][-1]['phase'], 'HELD')
        def stopped(session):
            self.assertEqual(process.poll(), 43)
            return dict(context=session.context, stopped=True,
                        process_identity_sha256=hashlib.sha256((str(process.pid)+code).encode()).hexdigest())
        def verified(session, _):
            session.assert_held('e'*64, 'b'*40, 'c'*64, 'recover')
            return dict(context=session.context, outcome='ROLLED_BACK', evidence_sha256='5'*64)
        child.compensate('a2'*32, lambda s: s.assert_held('e'*64, 'b'*40, 'c'*64, 'recover'),
                         verified, confirm_stopped=stopped)
        self.assertFalse(authority.blocked(self.conn))


if __name__ == '__main__':
    unittest.main()
