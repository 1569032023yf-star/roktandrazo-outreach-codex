"""Actual host HTTP to existing lease/backend / 真实宿主到原锁与后端链。"""
from contextlib import contextmanager
import json
from pathlib import Path
import threading
import time
import unittest
import urllib.error
from autonomy.inventory_event_bridge import ExistingOwnerBridge,EventMailbox,owner_observer
from autonomy.lock_recovery import exclusive_lock
from autonomy.release_store import ReleaseStore,build_bundle,sha
from autonomy.u1_host_runtime import open_host
from autonomy.unattended_policy import INVENTORY
import test_process_backend as backend_fixtures


class EventBridgeTests(unittest.TestCase):
    def setUp(self):
        self.backend_fixture=backend_fixtures.BackendTests('runTest');self.backend_fixture.setUp();self.addCleanup(self.backend_fixture.doCleanups)
        self.f=self.backend_fixture.f
        self.f.adapter.backend=self.backend_fixture.backend();self.f.adapter.monotonic=time.monotonic
        self.release=self.f.root/'release';self.state=self.f.root/'host-state';self.release.mkdir();self.state.mkdir()
        version=build_bundle(self.f.root/'package',{'app/main.py':b'pass\n'},'a'*40)
        store=ReleaseStore(self.release);store.stage(self.f.root/'package',version);store.activate(version,expected_current=None)
        self.token='u1_event_'+('a'*40)

    @contextmanager
    def host(self):
        with open_host(self.release,self.state,self.token,int(time.time())+60,b'fixture',sha(b'fixture'),port=0,event_runtime=self.f.runtime) as server:
            worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});worker.start()
            try:yield ExistingOwnerBridge(self.f.adapter,port=server.server_port,token=self.token)
            finally:server.shutdown();worker.join(3)

    def event(self):
        return dict(inventory_id=INVENTORY,admission=self.f.admission(),schedule=self.f.plan,idle=self.f.idle,budget_request=self.f.request)

    def test_actual_service_event_existing_owner_child_and_settlement(self):
        with self.host() as bridge,exclusive_lock(self.f.runtime):
            event=self.event();result=bridge.consume(event)
            self.assertEqual(result['owner_result']['outcome'],'COMPLETED');self.assertFalse(result['transport_terminal_accepted'])
            self.assertEqual(self.backend_fixture.marker.read_text(),'called\n')
            with self.assertRaises(urllib.error.HTTPError):bridge.consume(event)
            status=bridge.request('/v1/inventory-events/'+result['event_id']+'/status',{})
            self.assertEqual(status['transport_state'],'OWNER_REPORTED');self.assertEqual(status['execution_terminal'],'UNKNOWN')
            self.assertEqual(self.backend_fixture.marker.read_text(),'called\n')

    def test_reserved_after_process_loss_reopen_cannot_dispatch(self):
        with self.host() as bridge,exclusive_lock(self.f.runtime):
            event=self.event();owner=self.f.adapter._lock()
            identity=bridge.request('/v1/inventory-events',dict(event=event,owner=owner))['event_id']
            bridge.request('/v1/inventory-events/'+identity+'/reserve',dict(owner=owner))
            reopened=EventMailbox(self.state/'inventory-events.sqlite',observe_owner=owner_observer(self.f.runtime))
            self.assertEqual(reopened.status(identity)['execution_terminal'],'UNKNOWN')
            with self.assertRaisesRegex(ValueError,'NO_EVENT_REPLAY'):reopened.reserve(identity,owner)
            with self.assertRaises(urllib.error.HTTPError):bridge.consume(event)
            self.assertFalse(self.backend_fixture.marker.exists())

    def test_no_lease_foreign_owner_bad_auth_and_bad_admission(self):
        with self.host() as bridge:
            with self.assertRaisesRegex(RuntimeError,'EXPECTED_LOCK'):bridge.consume({})
            with exclusive_lock(self.f.runtime):
                event=self.event()
                bad=ExistingOwnerBridge(self.f.adapter,port=bridge.port,token='b'*40)
                with self.assertRaises(urllib.error.HTTPError) as caught:bad.consume(event)
                self.assertEqual(caught.exception.code,401)
                with self.assertRaises(urllib.error.HTTPError):bridge.request('/v1/inventory-events',dict(event=event,owner={}))
                event['admission']=self.f.admission(gates={})
                with self.assertRaises(RuntimeError):bridge.consume(event)
                self.assertFalse(self.backend_fixture.marker.exists())

    def test_lost_report_does_not_repeat_completed_child(self):
        with self.host() as bridge,exclusive_lock(self.f.runtime):
            original=bridge.request
            def lost_report(route,value):
                if route.endswith('/report'):raise OSError('injected transport loss')
                return original(route,value)
            bridge.request=lost_report;event=self.event()
            with self.assertRaises(OSError):bridge.consume(event)
            self.assertEqual(self.backend_fixture.marker.read_text(),'called\n')

            bridge.request=original
            with self.assertRaises(urllib.error.HTTPError):bridge.consume(event)
            self.assertEqual(self.backend_fixture.marker.read_text(),'called\n')

    def test_expiry_during_reserve_withholds_event_and_preserves_reservation(self):
        from http.server import HTTPServer
        from autonomy.host_readonly_http import readonly_handler
        from autonomy.inventory_event_bridge import event_handler
        clock=[10];expire=[False];owner={'lock_token_hash':'a'*64,'process_identity_hash':'b'*64}
        def observe():
            if expire[0]:clock[0]=12
            return owner
        mailbox=EventMailbox(self.state/'expiry.sqlite',observe_owner=observe)
        event=dict(inventory_id=INVENTORY,admission={},schedule={},idle={},budget_request={})
        identity=mailbox.submit(event,owner)
        base=readonly_handler(self.token,lambda _:None,credential_expires_at=11,clock=lambda:clock[0])
        with HTTPServer(('127.0.0.1',0),event_handler(base,mailbox)) as server:
            worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});worker.start()
            try:
                bridge=ExistingOwnerBridge(self.f.adapter,port=server.server_port,token=self.token)
                expire[0]=True
                with self.assertRaises(urllib.error.HTTPError) as caught:bridge.request('/v1/inventory-events/'+identity+'/reserve',dict(owner=owner))
                self.assertEqual(caught.exception.code,401)
                self.assertEqual(mailbox.status(identity)['transport_state'],'RESERVED')
            finally:server.shutdown();worker.join(3)


if __name__=='__main__':unittest.main()
