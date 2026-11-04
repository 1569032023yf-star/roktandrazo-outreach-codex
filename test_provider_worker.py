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
            with self.assertRaises(ExecutionUnknown):b.execute_once(o,deadline_monotonic=time.monotonic()+.9)
            self.assertEqual(b.status(o['idempotency_key'])['transport_state'],'UNKNOWN')
            with self.assertRaisesRegex(ExecutionUnknown,'UNKNOWN_NO_REPLAY'):b.execute_once(o,deadline_monotonic=time.monotonic()+.9)
            self.assertFalse((root/'unused-cache').exists())
