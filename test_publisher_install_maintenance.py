"""Publisher maintenance lifecycle with actual isolated authority transactions."""
from contextlib import closing
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
        code = '''import json,os,sqlite3,sys
from publisher_channel.install_maintenance import InstallMaintenance
c=sqlite3.connect(sys.argv[1]);b=json.loads(sys.argv[2])
s=InstallMaintenance(c,b,target_operation_id='e'*64,action='install')
s.execute(lambda _:os._exit(41),lambda *_:None)
'''
        r = subprocess.run([sys.executable, '-B', '-c', code, str(self.db), json.dumps(self.binding)], timeout=15)
        self.assertEqual(r.returncode, 41)
        authority.assert_held(self.conn, self.binding)
        self.assertEqual(self.session._records()[0][-1]['phase'], 'INSTALL_INTENT')
        with self.assertRaisesRegex(ValueError, 'REPLAY'):
            self.session.execute(lambda _: self.fail('replayed'), self.proof)
        self.session.reconcile(self.proof)
        self.assertFalse(authority.blocked(self.conn))

    def test_release_commit_failure_keeps_authority_and_does_not_replay_install(self):
        conn = self.conn
        class FailedFinalCommit:
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


if __name__ == '__main__':
    unittest.main()
