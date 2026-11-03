"""Actual PS coordinator/authority IPC / 真实协调器与权威库跨进程核验。"""
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from autonomy import inventory_maintenance as authority
from autonomy.process_control import MaintenanceControl, ControlProtocolError, PREFIX
from autonomy.process_job import run_tree
from publisher_channel.install_maintenance import InstallMaintenance
import test_host_install_transaction as fixture


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.host=fixture.HostInstallTests(); self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.conn=sqlite3.connect(self.host.root/'authority.db');self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)')
        self.conn.commit()
        self.binding=dict(inventory_id='1784775229336',operation_id='1'*64,source_commit='b'*40,
                          manifest_sha256='a'*64,lease_nonce='2'*64)
        self.session=InstallMaintenance(self.conn,self.binding,target_operation_id='a'*64,action='install')

    def request(self, sequence=0, **updates):
        value=dict(schema='rokt.u1-maintenance-check.v1',sequence=sequence,
                   target_operation_id='a'*64,source_commit='b'*40,manifest_sha256='a'*64,action='install')
        value.update(updates)
        return PREFIX+json.dumps(value,separators=(',',':')).encode()

    def test_real_coordinator_asks_live_authority_through_commit_then_releases(self):
        checks=[]
        def install(session):
            result=self.host.run_coordinator(maintenance_session=session)
            self.host.assert_ok(result);self.assertTrue(result.cleanup_verified)
            checks.extend(line for line in result.stdout.splitlines() if line.startswith(PREFIX.decode()))
            return result
        def verify(session, observed):
            # Fixture verifier: real files/journal; SCM and ACL remain doubles.
            rows=[json.loads(x) for x in (self.host.audit/('install-'+'a'*64+'.jsonl')).read_text().splitlines()]
            self.assertEqual(rows[-1]['phase'],'COMMITTED')
            self.assertEqual((self.host.code/'service/RoktU1Bridge.exe').read_bytes(),b'MZ-a')
            self.assertTrue(authority.blocked(self.conn));self.assertTrue(observed.cleanup_verified)
            return dict(context=session.context,outcome='COMMITTED',evidence_sha256='f'*64)
        self.session.execute(install,verify)
        self.assertGreater(len(checks),15)
        self.assertEqual([json.loads(x[len(PREFIX):])['sequence'] for x in checks],list(range(len(checks))))
        self.assertFalse(authority.blocked(self.conn))

    def test_denied_live_check_after_files_never_creates_service_or_releases(self):
        verified=[]
        with self.assertRaises(ControlProtocolError) as caught:
            self.session.execute(lambda s:self.host.run_coordinator(maintenance_session=s,
                control_deny_phase='FILES_VERIFIED'),lambda *args:verified.append(args))
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertTrue((self.host.code/'service/RoktU1Bridge.exe').exists())
        self.assertFalse((self.host.root/'service.json').exists())
        self.assertEqual(verified,[])
        authority.assert_held(self.conn,self.binding)
        self.assertEqual(self.session._records()[0][-1]['phase'],'UNKNOWN')

    def test_wrong_action_replay_duplicate_json_and_overlapping_requests_refused(self):
        self.session.acquire();self.session._transition('INSTALL_INTENT')
        writer=io.BytesIO();control=MaintenanceControl(self.session.maintenance_handler(),writer)
        control.offer(self.request(action='rollback'))
        with self.assertRaisesRegex(ValueError,'BINDING_MISMATCH'):control.poll()
        self.assertEqual(writer.getvalue(),b'')
        control.offer(self.request());control.poll()
        self.assertEqual(writer.getvalue(),b'{"sequence":0,"held":true}\n')
        control.offer(self.request())
        with self.assertRaisesRegex(ControlProtocolError,'SEQUENCE'):control.poll()
        control.offer(self.request(1)[:-1]+b',"sequence":1}')
        with self.assertRaises(ControlProtocolError):control.poll()
        control.offer(self.request(1))
        with self.assertRaisesRegex(ControlProtocolError,'OVERLAP'):control.offer(self.request(2))

    def test_child_eof_torn_requests_and_unacknowledged_exit_are_unknown(self):
        self.session.acquire();self.session._transition('INSTALL_INTENT')
        for payload in (self.request(),self.request()+b'\n'):
            with self.subTest(payload=payload[-1:]):
                # Emit and exit without reading. Success is impossible even if
                # the child wins the race with the parent's pipe acknowledgement.
                code='import os;os.write(1,'+repr(payload)+')'
                # A request+LF can be acknowledged just before exit; that is a
                # valid check, not an install success or release proof.
                if payload.endswith(b'\n'):
                    result=None
                    try:result=run_tree([sys.executable,'-c',code],timeout=3,
                        maintenance_handler=self.session.maintenance_handler())
                    except (ControlProtocolError,BrokenPipeError,OSError) as error:
                        self.assertTrue(error.cleanup_verified)
                    if result is not None:self.assertTrue(result.cleanup_verified)
                else:
                    with self.assertRaises(ControlProtocolError) as caught:
                        run_tree([sys.executable,'-c',code],timeout=3,
                                 maintenance_handler=self.session.maintenance_handler())
                    self.assertTrue(caught.exception.cleanup_verified)
                authority.assert_held(self.conn,self.binding)

    def test_nonreading_child_cannot_block_parent_deadline_or_cleanup(self):
        import time
        from autonomy.process_control import MAX_REQUESTS
        self.session.acquire();self.session._transition('INSTALL_INTENT')
        # Keep each request below the queue-overlap threshold while never
        # reading stdin. Once replies fill the pipe, the parent must fail closed.
        value=self.request().decode()
        code=('import os,time,json;v=json.loads('+repr(value[len(PREFIX):])+');'
              '\nfor i in range('+str(MAX_REQUESTS)+'):\n v["sequence"]=i;'
              'os.write(1,b"U1_MAINTENANCE:"+json.dumps(v).encode()+b"\\n");time.sleep(.025)')
        start=time.monotonic()
        with self.assertRaises((ControlProtocolError,BlockingIOError,subprocess.TimeoutExpired,OSError)) as caught:
            run_tree([sys.executable,'-c',code],timeout=8,
                     maintenance_handler=self.session.maintenance_handler())
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertLess(time.monotonic()-start,12)
        authority.assert_held(self.conn,self.binding)


if __name__=='__main__':unittest.main()
