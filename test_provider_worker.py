import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from autonomy.process_backend import ProcessBackend, ExecutionUnknown
import test_process_backend as fixtures


class ProviderWorkerTests(unittest.TestCase):
    def config(self, root):
        p=root/'provider.json'
        p.write_text(json.dumps({'schema':'rokt.provider-environment.v1','environment':{
            'WORKBUDDY_DISCOVERY_PROVIDER':'browser_maps','BROWSER_MAPS_MODE':'file',
            'BROWSER_MAPS_CACHE_DIR':str(root/'unused-cache')}}),encoding='utf-8')
        return p,hashlib.sha256(p.read_bytes()).hexdigest()

    def test_isolated_entrypoint_preflight_uses_real_adapter_without_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,h=self.config(root)
            worker=Path('autonomy/provider_worker.py').absolute()
            r=subprocess.run([sys.executable,'-I','-B',str(worker),'--provider-config',str(p),'--provider-config-sha256',h,'--preflight'],capture_output=True,text=True,timeout=20,cwd=d)
            self.assertEqual(r.returncode,0,r.stderr)
            v=json.loads(r.stdout);self.assertEqual(v['provider'],'browser_maps')
            self.assertEqual(v['contract']['status'],'CONTRACT_MISSING')
            self.assertFalse(v['dispatch_authorized']);self.assertFalse((root/'unused-cache').exists())
            self.assertNotIn('slot_receipt',v);self.assertNotIn('budget_receipt',v)

    def test_bad_digest_rejected_without_leaking_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            p,h=self.config(Path(d));p.write_text('SECRET_NOT_FOR_OUTPUT',encoding='utf-8')
            r=subprocess.run([sys.executable,'-I','-B',str(Path('autonomy/provider_worker.py').absolute()),'--provider-config',str(p),'--provider-config-sha256',h,'--preflight'],capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,65);self.assertEqual(r.stdout,'')
            self.assertEqual(r.stderr.strip(),'PROVIDER_WORKER_INPUT_REJECTED')

    def test_real_backend_worker_refusal_is_durable_unknown_and_never_replayed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,h=self.config(root);worker=Path('autonomy/provider_worker.py').absolute()
            b=ProcessBackend.for_provider_worker(root/'backend.sqlite',python=sys.executable,
                python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),backend_id='synthetic-backend',
                provider_config=str(p),provider_config_sha256=h)
            o=fixtures.BackendTests.operation(self)
            from autonomy.growth_ledger import digest
            o.pop('idempotency_key');o['provider_request']=dict(provider='browser_maps',query='coffee',city='Example City',state='TN',page_cursor='',page_size=1);o['idempotency_key']=digest(o)
            with self.assertRaises(ExecutionUnknown):b.execute_once(o,deadline_monotonic=time.monotonic()+.9)
            self.assertEqual(b.status(o['idempotency_key'])['transport_state'],'UNKNOWN')
            with self.assertRaisesRegex(ExecutionUnknown,'UNKNOWN_NO_REPLAY'):b.execute_once(o,deadline_monotonic=time.monotonic()+.9)
            self.assertFalse((root/'unused-cache').exists())


class WorkerOperationTests(unittest.TestCase):
    def encode(self, updates=None):
        from autonomy.growth_ledger import digest
        o=fixtures.BackendTests.operation(self);o.pop('idempotency_key')
        o.update(updates or {});o['idempotency_key']=digest(o)
        return json.dumps(o).encode()

    def test_existing_backend_operation_is_consumed_and_retained(self):
        import io
        from autonomy.provider_worker import read_operation
        raw=self.encode();self.assertEqual(read_operation(io.BytesIO(raw)),json.loads(raw))

    def test_duplicates_oversize_nonfinite_and_modified_binding_are_rejected(self):
        import io
        from autonomy.provider_worker import read_operation
        for raw in (b'x'*65537,b'{}',b'{"x":1,"x":2}',b'{"x":NaN}',self.encode().replace(b'isolated_offline',b'production_live')):
            with self.subTest(raw_size=len(raw)),self.assertRaises(ValueError):read_operation(io.BytesIO(raw))

    def test_original_claim_join_checks_actual_token_and_rejects_partial_join(self):
        import io
        from autonomy.growth_ledger import digest
        from autonomy.provider_worker import read_operation
        c=dict(slot='slot',epoch=1,owner='owner',run_id='run',request_id='request')
        hashes={k:'a'*64 for k in ('original_event_digest','lock_token_hash','process_identity_hash','runtime_id','slots_id','budget_id')}
        extra=dict(c,token='token',**hashes,original_claim_digest=digest(dict(c,claim_token_hash=digest('token'))))
        self.assertEqual(read_operation(io.BytesIO(self.encode(extra)))['run_id'],'run')
        for patch in (dict(original_event_digest='a'*64),dict(extra,token='different-token')):
            with self.assertRaises(ValueError):read_operation(io.BytesIO(self.encode(patch)))

    def test_invalid_operation_rejected_before_adapter_construction(self):
        import io
        from unittest.mock import patch
        from autonomy.provider_worker import main
        with patch('autonomy.provider_worker.sys.stdin',io.TextIOWrapper(io.BytesIO(b'{}'))),patch('autonomy.provider_worker.pinned_provider_adapter') as adapter,patch('autonomy.provider_worker.sys.stderr',io.StringIO()) as errors:
            self.assertEqual(main(['--provider-config','not-used','--provider-config-sha256','bad']),65)
            adapter.assert_not_called();self.assertEqual(errors.getvalue().strip(),'PROVIDER_WORKER_INPUT_REJECTED')


class BoundSearchRequestTests(unittest.TestCase):
    def request(self, **changes):
        value=dict(provider='google_places',query='coffee shops',city='Example City',
                   state='TN',page_cursor='',page_size=20)
        value.update(changes)
        return value

    def test_reject_disabled_provider_ambiguous_parameters_and_implicit_defaults(self):
        from discovery.providers.contracts import bound_search_request
        good=self.request();self.assertEqual(bound_search_request(good),good)
        bad=[self.request(provider='serpapi_maps'),self.request(page_size=True),
             self.request(page_size=21),self.request(city=' '),self.request(query='x\n'),
             self.request(page_cursor='x'*8193),dict(good,api_key='forbidden')]
        missing=dict(good);missing.pop('page_size');bad.append(missing)
        for value in bad:
            with self.subTest(keys=list(value)),self.assertRaises(ValueError):bound_search_request(value)

    def test_signed_admission_carries_request_into_backend_digest(self):
        import test_single_slot_adapter as slot
        from autonomy.lock_recovery import exclusive_lock
        from autonomy.growth_ledger import digest
        c=slot.SingleSlotTests();c.setUp()
        try:
            with exclusive_lock(c.runtime):
                self.assertEqual(c.run_one(c.admission(provider_request=self.request()))['outcome'],'COMPLETED')
                operation=dict(c.backend.operation);key=operation.pop('idempotency_key')
                self.assertEqual(operation['provider_request'],self.request())
                self.assertEqual(key,digest(operation))
                operation['provider_request']['city']='another city'
                self.assertNotEqual(key,digest(operation))
        finally:c.doCleanups()

    def test_invalid_signed_request_rejected_before_budget_or_claim(self):
        import test_single_slot_adapter as slot
        from autonomy.lock_recovery import exclusive_lock
        c=slot.SingleSlotTests();c.setUp()
        try:
            with exclusive_lock(c.runtime),self.assertRaises(ValueError):
                c.run_one(c.admission(provider_request=self.request(provider='serpapi_maps')))
            self.assertEqual(c.backend.calls,0);self.assertEqual(c.slots.snapshot(),[])
            with c.budget.tx() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],0)
        finally:c.doCleanups()

    def test_worker_rejects_configured_provider_mismatch_without_request(self):
        import io
        from contextlib import contextmanager
        from unittest.mock import patch
        from autonomy.provider_worker import main
        raw=WorkerOperationTests().encode(dict(provider_request=self.request()))
        class Adapter:provider_name='browser_maps'
        @contextmanager
        def configured(*args):yield Adapter()
        with patch('autonomy.provider_worker.sys.stdin',io.TextIOWrapper(io.BytesIO(raw))),patch('autonomy.provider_worker.pinned_provider_adapter',configured),patch('autonomy.provider_worker.sys.stderr',io.StringIO()) as errors:
            self.assertEqual(main(['--provider-config','unused','--provider-config-sha256','unused']),65)
            self.assertEqual(errors.getvalue().strip(),'PROVIDER_WORKER_INPUT_REJECTED')


class WorkerAdmissionBoundaryTests(unittest.TestCase):
    def test_every_partial_original_binding_is_rejected(self):
        import io
        from autonomy.provider_worker import read_operation
        for field in ('original_event_digest', 'original_claim_digest',
                      'lock_token_hash', 'process_identity_hash',
                      'runtime_id', 'slots_id', 'budget_id'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                read_operation(io.BytesIO(WorkerOperationTests().encode({field: 'a'*64})))

    def test_missing_search_rejected_before_provider_configuration(self):
        import io
        from unittest.mock import patch
        from autonomy.provider_worker import main
        raw = WorkerOperationTests().encode()
        with patch('autonomy.provider_worker.sys.stdin', io.TextIOWrapper(io.BytesIO(raw))), \
             patch('autonomy.provider_worker.pinned_provider_adapter') as adapter, \
             patch('autonomy.provider_worker.sys.stderr', io.StringIO()) as errors:
            self.assertEqual(main(['--provider-config','unused','--provider-config-sha256','unused']), 65)
            adapter.assert_not_called()
            self.assertEqual(errors.getvalue().strip(), 'PROVIDER_WORKER_INPUT_REJECTED')
