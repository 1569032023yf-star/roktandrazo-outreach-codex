"""真实临时回环HTTP契约 / Real ephemeral loopback HTTP contracts."""
import http.client
import json
import threading
import unittest
from http.server import HTTPServer
from autonomy.host_readonly_http import readonly_handler
from autonomy.host_readonly_http import snapshot_status_reader
from autonomy.recovery_status import inspect_recovery_status
import test_recovery_status as fixtures
import hashlib


class HostReadOnlyHTTPTests(unittest.TestCase):
    def setUp(self):
        self.raw=fixtures.RecoveryStatusTests().image()
        self.digest=hashlib.sha256(self.raw).hexdigest()
        self.calls=[];self.value=inspect_recovery_status(self.raw,self.digest,'a'*64)
        self.token='offline-fixture-token-'+'a'*32
        def read(operation):
            self.calls.append(operation)
            if isinstance(self.value,Exception):raise self.value
            return self.value
        self.now=1000
        self.clock_error=False
        def clock():
            if self.clock_error:raise RuntimeError('clock unavailable')
            return self.now
        self.server=HTTPServer(('127.0.0.1',0),readonly_handler(self.token,read,
            credential_expires_at=1100,clock=clock))
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.01})
        self.thread.start();self.addCleanup(self.close)

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(5)
        self.assertFalse(self.thread.is_alive())

    def request(self,path,method='GET',auth=True,headers=None):
        connection=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        try:
            h={'Authorization':'Bearer '+self.token} if auth else {}
            if headers:h.update(headers)
            connection.request(method,path,headers=h)
            response=connection.getresponse();raw=response.read()
            result=json.loads(raw) if raw else {}
            if result:
                for key in ('allow_dispatch','allow_cancel_dispatch','allow_reconcile','production_accepted'):
                    self.assertIs(result[key],False)
                self.assertNotIn(self.token,raw.decode())
            return response.status,result
        finally:connection.close()

    def test_authentication_precedes_health_or_backend_reads(self):
        for path in ('/v1/health','/v1/recovery-status/'+'a'*64):
            self.assertEqual(self.request(path,auth=False)[0],401)
            self.assertEqual(self.request(path,headers={'Authorization':'Bearer wrong'})[0],401)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.request('/v1/health')[0],200)
        self.assertEqual(self.calls,[])

    def test_existing_operation_status_never_replays_unknown(self):
        operation='a'*64
        for state in ('PREPARED','COMPLETED'):
            raw=fixtures.RecoveryStatusTests().image(state=state)
            self.value=snapshot_status_reader(raw,hashlib.sha256(raw).hexdigest())(operation)
            code,result=self.request('/v1/recovery-status/'+operation)
            self.assertEqual(code,200);self.assertEqual(result['journal_phase'],state)
            self.assertEqual(result['execution_terminal'],'UNKNOWN')
            self.assertFalse(result['replay_allowed'])
        self.value=snapshot_status_reader(self.raw,self.digest)('b'*64)
        code,result=self.request('/v1/recovery-status/'+'b'*64)
        self.assertEqual(code,200);self.assertEqual(result['journal_phase'],'NOT_RECORDED')
        self.assertEqual(self.calls,[operation]*2+['b'*64])

    def test_invalid_backend_or_methods_routes_and_body_fail_closed(self):
        for value in (True,{},'RUNNING',RuntimeError('secret-backend-details')):
            self.value=value;code,result=self.request('/v1/recovery-status/'+'c'*64)
            self.assertEqual(code,503);self.assertNotIn('secret-backend-details',str(result))
        before=list(self.calls)
        for path in ('/v1/apply','/v1/recovery-status/../x','/v1/recovery-status/'+'c'*64+'?execute=true'):
            self.assertEqual(self.request(path)[0],404)
        for method in ('POST','PUT','DELETE','PATCH'):
            self.assertEqual(self.request('/v1/health',method)[0],405)
        self.assertEqual(self.request('/v1/health',headers={'Content-Length':'1'})[0],400)
        self.assertEqual(self.request('/v1/health',headers={'Transfer-Encoding':'chunked'})[0],400)
        self.assertEqual(self.calls,before)

    def test_hash_failure_and_forged_authority_never_become_http_success(self):
        self.value=snapshot_status_reader(self.raw,'0'*64)('a'*64)
        self.assertEqual(self.request('/v1/recovery-status/'+'a'*64)[0],503)
        good=inspect_recovery_status(self.raw,self.digest,'a'*64)
        for change in ({'execution_terminal':'completed'},{'allow_reconcile':True},
                       {'accepted':1},{'source_authorized':True},{'extra':'secret'}):
            self.value=dict(good,**change)
            self.assertEqual(self.request('/v1/recovery-status/'+'a'*64)[0],503)

    def test_empty_or_invalid_provisioning_rejected(self):
        for token in ('','short','a'*32+'\r\n'):
            with self.assertRaises(ValueError):readonly_handler(token,lambda _: 'UNKNOWN',credential_expires_at=1100)

    def test_expired_and_invalid_clock_reject_before_any_backend_read(self):
        for now in (1100,1101,-1,True,float('nan'),float('inf'),None):
            self.now=now
            for method in ('GET','POST','HEAD'):
                self.assertEqual(self.request('/v1/recovery-status/'+'a'*64,method)[0],401)
        self.assertEqual(self.calls,[])

    def test_explicit_deadline_required_and_head_has_no_body(self):
        for expiry in (None,True,0,-1,1100.0):
            with self.assertRaises(ValueError):readonly_handler(self.token,lambda _: {},credential_expires_at=expiry)
        self.assertEqual(self.request('/v1/health','HEAD'),(405,{}))
        self.assertEqual(self.request('/v1/health','POST',auth=False)[0],401)
        self.assertEqual(self.calls,[])

    def test_clock_rollback_permanently_fences_credential_across_requests(self):
        path='/v1/recovery-status/'+'a'*64
        self.assertEqual(self.request(path)[0],200)
        self.now=999
        self.assertEqual(self.request(path)[0],401)
        self.now=1001
        self.assertEqual(self.request(path)[0],401)
        self.assertEqual(self.calls,['a'*64])

    def test_expiry_cannot_be_revived_by_clock_rollback(self):
        self.now=1100
        self.assertEqual(self.request('/v1/health')[0],401)
        self.now=1000
        self.assertEqual(self.request('/v1/recovery-status/'+'a'*64)[0],401)
        self.assertEqual(self.calls,[])

    def test_failed_clock_remains_fenced_after_clock_recovers(self):
        self.clock_error=True
        self.assertEqual(self.request('/v1/health')[0],401)
        self.clock_error=False
        self.assertEqual(self.request('/v1/recovery-status/'+'a'*64)[0],401)
        self.assertEqual(self.calls,[])

    def test_duplicate_authorization_rejected_without_backend_read(self):
        connection=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        try:
            connection.putrequest('GET','/v1/recovery-status/'+'a'*64)
            connection.putheader('Authorization','Bearer '+self.token)
            connection.putheader('Authorization','Bearer '+self.token)
            connection.endheaders();response=connection.getresponse()
            self.assertEqual(response.status,401);response.read()
            self.assertEqual(self.calls,[])
        finally:connection.close()


if __name__=='__main__':unittest.main()
