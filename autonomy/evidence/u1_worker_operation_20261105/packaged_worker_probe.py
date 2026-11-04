"""包内真实Worker只读探针 / Packaged real Worker offline probe."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
root=Path.cwd();e=Path(__file__).resolve().parent
bundle=root.parent/'u1-operation-extracted-6de5cf3';payload=bundle/'payload'
manifest=json.loads((bundle/'manifest.json').read_text())
source='6de5cf3d421e0073be905a57e0dd3cd2cc1024a6'
assert manifest['source_commit']==source
python=payload/'host/runtime/python/python.exe';worker=payload/'python/autonomy/provider_worker.py'
for p in (python,worker):assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest['files'][p.relative_to(payload).as_posix()]
code=r"""
import hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
app=Path(sys.argv[1]);sys.path.insert(0,str(app))
from autonomy.process_backend import ProcessBackend,ExecutionUnknown
from autonomy.growth_ledger import digest
from autonomy.single_slot_adapter import BACKEND_PROTOCOL,OPERATION_SCHEMA
from autonomy.unattended_policy import INVENTORY
with tempfile.TemporaryDirectory(prefix='u1-worker-probe-') as d:
 root=Path(d);config=root/'provider.json'
 config.write_text(json.dumps({'schema':'rokt.provider-environment.v1','environment':{'WORKBUDDY_DISCOVERY_PROVIDER':'browser_maps','BROWSER_MAPS_MODE':'file','BROWSER_MAPS_CACHE_DIR':str(root/'unused-cache')}}),encoding='utf-8')
 h=hashlib.sha256(config.read_bytes()).hexdigest();worker=app/'autonomy/provider_worker.py'
 base=[sys.executable,'-I','-B',str(worker),'--provider-config',str(config),'--provider-config-sha256',h]
 r=subprocess.run(base+['--preflight'],capture_output=True,text=True,cwd=d,timeout=20)
 assert r.returncode==0,r.stderr
 v=json.loads(r.stdout);assert v['provider']=='browser_maps' and v['contract']['status']=='CONTRACT_MISSING' and not v['dispatch_authorized']
 o=dict(schema=OPERATION_SCHEMA,scope='isolated_offline',production_execution=False,inventory_id=INVENTORY,backend_protocol=BACKEND_PROTOCOL,backend_id='isolated-worker-probe',max_wall_seconds=5);o['idempotency_key']=digest(o)
 r=subprocess.run(base,input=json.dumps(o),capture_output=True,text=True,cwd=d,timeout=20)
 assert r.returncode==78 and not r.stdout
 assert json.loads(r.stderr)['external_request_started'] is False
 assert json.loads(r.stderr)['operation_digest_checked'] is True
 r=subprocess.run(base,input='{}',capture_output=True,text=True,cwd=d,timeout=20)
 assert r.returncode==65 and not r.stdout and r.stderr.strip()=='PROVIDER_WORKER_INPUT_REJECTED'
 backend=ProcessBackend.for_provider_worker(root/'journal.sqlite',python=sys.executable,python_sha256=sys.argv[2],worker_sha256=sys.argv[3],backend_id='isolated-worker-probe',provider_config=str(config),provider_config_sha256=h)
 try:backend.execute_once(o,deadline_monotonic=time.monotonic()+4)
 except ExecutionUnknown:pass
 else:raise AssertionError('refusal accepted as receipt')
 assert backend.status(o['idempotency_key'])['transport_state']=='UNKNOWN'
 try:backend.execute_once(o,deadline_monotonic=time.monotonic()+4)
 except ExecutionUnknown as x:assert str(x)=='UNKNOWN_NO_REPLAY'
 else:raise AssertionError('replayed')
 assert not (root/'unused-cache').exists()
 print(json.dumps(dict(real_packaged_cpython=True,preflight=True,operation_digest_checked=True,malformed_input_rejected=True,contract_refusal=True,persistent_unknown=True,replay_denied=True,external_requests=0,production_execution=False)))
"""
r=subprocess.run([str(python),'-I','-B','-c',code,str(payload/'python'),manifest['files']['host/runtime/python/python.exe'],manifest['files']['python/autonomy/provider_worker.py']],capture_output=True,text=True,timeout=90)
(e/'PACKAGED_WORKER_OUTPUT.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
result=dict(source_commit=source,outcome='PASSED' if r.returncode==0 else 'FAILED',returncode=r.returncode,production_execution=False)
if r.returncode==0:result['checks']=json.loads(r.stdout)
(e/'PACKAGED_WORKER_REPORT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));raise SystemExit(r.returncode)
