"""Original DB owner -> real loopback host -> slot/budget chain, isolated only."""
from contextlib import closing, contextmanager
import json
import os
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

import bd_db
from autonomy import inventory_maintenance as maintenance
from autonomy.inventory_event_bridge import ExistingOwnerBridge, EventMailbox
from autonomy.original_inventory_owner import OriginalOwnerAuthority, observer, session_key
from autonomy.release_store import ReleaseStore, build_bundle, sha
from autonomy.single_slot_adapter import OriginalOwnerSlotAdapter
from autonomy.u1_host_runtime import open_host
from autonomy.unattended_policy import INVENTORY
import test_single_slot_adapter as slot_fixtures
from test_growth_ledger import T


class OriginalOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f = slot_fixtures.SingleSlotTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.path = self.f.root/'original.sqlite'
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)')
            conn.commit()
        self.connect = lambda: sqlite3.connect(self.path, timeout=2)
        self.ro = lambda: sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True, timeout=2)
        self.mock = patch.object(bd_db, 'get_db', self.connect)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.day = 'inventory:2026-11-03'
        self.holder = 'original-run'
        self.captured=bd_db.acquire_run_lock(self.day, self.holder,capture_owner=True)
        self.assertTrue(self.captured)
        self.authority = OriginalOwnerAuthority(self.connect)
        self.observe = observer(self.ro)
        self.f.adapter = OriginalOwnerSlotAdapter(self.f.slots, self.f.budget,
            original_owner=self.authority, target=self.f.target, consumer=self.f.trust,
            backend=self.f.backend, wall_clock=lambda:T+10, monotonic=lambda:1)

    def event(self):
        return dict(inventory_id=INVENTORY, admission=self.f.admission(),
                    schedule=self.f.plan, idle=self.f.idle, budget_request=self.f.request)

    def release(self, expected=None):
        return bd_db.release_run_lock(self.day,self.holder,
            expected_owner=self.captured if expected is None else expected)

    def session(self):
        with closing(self.connect()) as conn:
            return json.loads(conn.execute('SELECT value FROM system_config WHERE key=?',
                (session_key(maintenance.PREFIX+self.day),)).fetchone()[0])

    def replace_session(self, **changes):
        session = self.session()
        session.update(changes)
        with closing(self.connect()) as conn:
            conn.execute('UPDATE system_config SET value=? WHERE key=?',
                (json.dumps(session), session_key(maintenance.PREFIX+self.day)))
            conn.commit()

    @contextmanager
    def host(self):
        release=self.f.root/'release'; state=self.f.root/'host-state'
        release.mkdir(); state.mkdir()
        version=build_bundle(self.f.root/'package', {'app/main.py':b'pass\n'}, 'a'*40)
        store=ReleaseStore(release)
        store.stage(self.f.root/'package',version); store.activate(version,expected_current=None)
        token='original_owner_'+('a'*40)
        with patch.dict(os.environ,{'ROKT_DEV_ALLOW_LOOPBACK':'1'}), open_host(release,state,token,int(time.time())+60,b'fixture',sha(b'fixture'),
                       port=0,original_owner_connect=self.ro) as server:
            worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01})
            worker.start()
            try:
                yield ExistingOwnerBridge(self.f.adapter,port=server.server_port,token=token)
            finally:
                server.shutdown(); worker.join(3)

    def test_real_http_original_owner_claim_backend_settlement_release(self):
        self.assertFalse((self.f.runtime/'supervisor.lock').exists())
        with self.host() as bridge:
            result=bridge.consume(self.event())
        self.assertEqual(result['owner_result']['outcome'],'COMPLETED')
        self.assertFalse(result['transport_terminal_accepted'])
        self.assertEqual(self.session()['tree_state'],'verified_closed')
        self.assertEqual(self.f.backend.calls,1)
        self.assertEqual(self.observe(),self.authority.check())
        self.assertTrue(self.release())
        with self.assertRaises(ValueError):self.observe()

    def test_lost_backend_result_blocks_release_maintenance_and_other_date(self):
        self.f.backend.mode='lost'
        with self.host() as bridge:
            result=bridge.consume(self.event())
        self.assertEqual(result['owner_result']['outcome'],'UNKNOWN_RECONCILE_ONLY')
        self.assertEqual(self.session()['tree_state'],'unverified')
        self.assertFalse(self.release())
        self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-04','other'))
        with closing(self.connect()) as conn:
            with self.assertRaisesRegex(ValueError,'NOT_QUIESCENT'):
                maintenance.acquire(conn,dict(inventory_id=INVENTORY,operation_id='a'*64,
                    source_commit='b'*40,manifest_sha256='c'*64,lease_nonce='d'*64))
        self.assertEqual(self.f.backend.calls,1)

    def test_partial_settlement_keeps_original_tree_and_lock(self):
        event=self.event()
        self.f.adapter.prepare_event(event)
        with patch.object(self.f.budget,'settle',side_effect=OSError('injected settlement failure')):
            result=self.f.run_one(event['admission'])
        self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
        self.assertEqual(self.session()['tree_state'],'unverified')
        self.assertFalse(self.release())
        self.assertEqual(self.f.backend.calls,1)
        # Read-only reconciliation consumes receipts; it never calls backend again.
        result=self.f.adapter.reconcile(self.f.admission(),**self.f.backend.receipts)
        self.assertEqual(result['outcome'],'COMPLETED')
        self.assertEqual(self.f.backend.calls,1)
        self.assertTrue(self.release())

    def test_old_incarnation_cannot_use_or_close_new_owner_even_same_run_id(self):
        old=self.authority
        self.assertTrue(self.release())
        new_capture=bd_db.acquire_run_lock(self.day,self.holder,capture_owner=True)
        self.assertTrue(new_capture)
        self.assertNotEqual(old.binding,self.observe())
        for action in (old.check,lambda:old.mark_tree('verified_closed')):
            with self.assertRaisesRegex(ValueError,'INCARNATION_CHANGED'):action()
        self.assertFalse(self.release())
        self.assertFalse(bd_db.release_run_lock(self.day,self.holder))
        self.assertTrue(self.release(new_capture))

    def test_pid_incarnation_or_corrupted_session_cannot_release(self):
        for changes in ({'process_identity':'unknown'}, {'nonce':'x'*64}, {'pid':True}):
            original=self.session()
            self.replace_session(**changes)
            with self.assertRaises(ValueError):self.observe()
            self.assertFalse(self.release())
            self.replace_session(**original)

    def test_reserved_event_lost_response_never_releases_for_reexecution(self):
        mailbox=EventMailbox(self.f.root/'mailbox.sqlite',observe_owner=self.observe)
        event=self.event(); owner=self.authority.check()
        self.f.adapter.prepare_event(event)
        identity=mailbox.submit(event,owner)
        mailbox.reserve(identity,owner)  # Caller dies before receiving bytes.
        with self.assertRaisesRegex(ValueError,'NO_EVENT_REPLAY'):mailbox.reserve(identity,owner)
        self.assertEqual(mailbox.status(identity)['execution_terminal'],'UNKNOWN')
        self.assertEqual(self.f.backend.calls,0)
        self.assertFalse(self.release())

    def test_observer_is_readonly_and_never_acquires_an_owner(self):
        before=self.session()
        self.assertEqual(self.observe(),self.authority.check())
        self.assertEqual(before,self.session())
        self.assertTrue(self.release())
        with self.assertRaises(ValueError):OriginalOwnerAuthority(self.connect)

    def test_database_copy_is_not_same_original_authority(self):
        duplicate=self.f.root/'copy.sqlite'
        with closing(self.connect()) as source,closing(sqlite3.connect(duplicate)) as dest:
            source.backup(dest)
        other=lambda:sqlite3.connect(duplicate)
        with self.assertRaisesRegex(ValueError,'IDENTITY_REJECTED'):OriginalOwnerAuthority(other)

    def test_old_receipts_cannot_close_new_owner_event(self):
        event=self.event(); self.f.adapter.prepare_event(event)
        self.assertEqual(self.f.run_one(event['admission'])['outcome'],'COMPLETED')
        old_receipts=self.f.backend.receipts
        self.assertTrue(self.release())
        self.captured=bd_db.acquire_run_lock(self.day,self.holder,capture_owner=True)
        self.authority=OriginalOwnerAuthority(self.connect)
        self.f.adapter=OriginalOwnerSlotAdapter(self.f.slots,self.f.budget,
            original_owner=self.authority,target=self.f.target,consumer=self.f.trust,
            backend=self.f.backend,wall_clock=lambda:T+10,monotonic=lambda:1)
        new_event=self.event(); self.f.adapter.prepare_event(new_event)
        with self.assertRaisesRegex(ValueError,'CLAIM_JOIN_REQUIRED'):
            self.f.adapter.reconcile(new_event['admission'],**old_receipts)
        self.assertEqual(self.session()['tree_state'],'unverified')
        self.assertFalse(self.release())
        self.assertEqual(self.f.backend.calls,1)

    def test_sqlite_sidecars_are_reserved_even_before_creation(self):
        from autonomy.single_slot_adapter import CancellationJournal,AdapterError
        protected=self.f.adapter._protected_paths()
        for database in protected:
            for suffix in ('','-journal','-wal','-shm'):
                with self.subTest(database=database,suffix=suffix):
                    journal=CancellationJournal(str(database)+suffix)
                    with self.assertRaisesRegex(AdapterError,'ALIAS_REJECTED'):
                        journal.checked_path(protected)

    def test_event_intent_precedes_transport_and_blocks_lost_submit_replay(self):
        bridge=ExistingOwnerBridge(self.f.adapter,port=8791,token='a'*40)
        event=self.event()
        with patch.object(bridge,'request',side_effect=ConnectionError('lost submit response')):
            with self.assertRaises(ConnectionError):bridge.consume(event)
            with self.assertRaisesRegex(ValueError,'EVENT_REPLAY'):bridge.consume(event)
        self.assertEqual(self.session()['tree_state'],'unverified')
        self.assertFalse(self.release())
        self.assertEqual(self.f.backend.calls,0)

    def test_actual_process_exit_after_event_intent_never_reclaims(self):
        import subprocess,sys
        self.assertTrue(self.release())
        code = '''import os,sqlite3,sys
import bd_db
from autonomy.original_inventory_owner import OriginalOwnerAuthority
connect=lambda:sqlite3.connect(sys.argv[1])
bd_db.get_db=connect
assert bd_db.acquire_run_lock('inventory:2026-11-04','child',capture_owner=True)
OriginalOwnerAuthority(connect).prepare_event('a'*64)
os._exit(29)
'''
        result=subprocess.run([sys.executable,'-B','-c',code,str(self.path)],
                              capture_output=True,timeout=20)
        self.assertEqual(result.returncode,29,result.stderr)
        with self.assertRaises(ValueError):self.observe()
        self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-05','restart'))
        self.assertFalse(bd_db.release_run_lock('inventory:2026-11-04','child',
                                              expected_owner=self.captured))


if __name__=='__main__':unittest.main()
