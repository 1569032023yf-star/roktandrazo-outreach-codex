"""Reproducible offline evidence verification; never accesses production."""
import hashlib,json,subprocess,sys,tempfile,time,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]
os.chdir(ROOT)
HERE=Path(__file__).parent
PIN='acdb1494ebb02f140e3ca0faf97aef82aa70a68f'
WB='54b79153adf8b8d6df1349e5ea78751bf244f24e'
def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=[]
for name,expected in [('WINDOWS_ENVIRONMENT_EVIDENCE_20261030.json','c2386c8fc10695c96a975a59fad7e0724ffc4649'),('WINDOWS_ENVIRONMENT_EVIDENCE_20261030.md','a623e0173a6b0ce59d693e9c8514803a4602bfe3')]:
    raw=(HERE/'source'/name).read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert actual==expected,(name,actual)
    files.append(dict(path='handoff/workbuddy/production/'+name,git_blob_sha=actual,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
s=json.loads((HERE/'source'/files[0]['path'].split('/')[-1]).read_text(encoding='utf-8'))
assert s['schema']=='rokt.windows_env_evidence.v1'
for key in ['operator_context','host','identity','service_logon_right','acl_baseline','proxy_unattended','bridge_runtime','publisher_recap','inventory_authority']:
    assert isinstance(s[key],dict),key
assert isinstance(s['non_claims'],list) and s['non_claims']
assert s['operator_context']['agent']=='workbuddy'
assert s['evidence_class']=='READ_ONLY_LOCAL_OBSERVATION'
assert datetime.fromisoformat(s['generated_at'])==datetime.fromisoformat(s['generated_at_utc'].replace('Z','+00:00'))
receipt=dict(workbuddy_commit=WB,files=files,verified_file_count=2,json_parse='PASS',declared_schema_structure='PASS',external_json_schema='NOT_SUPPLIED_NOT_CLAIMED',producer='workbuddy',sample_time_note='Individual sample times retained verbatim in source; report generation is not a fresh sample.',generated_at=s['generated_at'],git_commit_created_at='2026-10-30T07:11:55Z',commit_after_generation_seconds=100,production_resampled=False,producer_comment=6517133750,CODEX_HANDOFF_CONSUMED=False,publication='PENDING',source_commit=PIN)
receipt_path=HERE/'CONSUMPTION_RECEIPT.json'
if receipt_path.exists():
    existing=json.loads(receipt_path.read_text(encoding='utf-8'))
    if existing.get('CODEX_HANDOFF_CONSUMED'):
        assert existing['workbuddy_commit']==WB and existing['files']==files
    else:
        dump(receipt_path,receipt)
else:
    dump(receipt_path,receipt)
out=ROOT/'autonomy/evidence/host_http_expiry_20261030';out.mkdir(exist_ok=True)
old=json.loads((ROOT/'autonomy/evidence/host_readonly_http_20261030/SOURCE_MANIFEST.json').read_text())
manifest=[]
with tempfile.TemporaryDirectory(prefix='rokt-expiry-import-') as temp:
    target=Path(temp)
    for entry in old['files']:
        p=entry['path'];raw=subprocess.check_output(['git','show',PIN+':'+p]);dst=target/p;dst.parent.mkdir(exist_ok=True,parents=True);dst.write_bytes(raw)
        manifest.append(dict(path=p,git_blob_sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),sha256=hashlib.sha256(raw).hexdigest()))
    result=subprocess.run([sys.executable,'-B','-c','import autonomy.host_readonly_http, autonomy.recovery_status'],cwd=target,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
dump(out/'SOURCE_MANIFEST.json',dict(source_commit=PIN,files=manifest,isolated_import='PASS',production_package_changed=False))
start=time.monotonic()
result=subprocess.run([sys.executable,'-B','-m','unittest','test_host_readonly_http','test_recovery_status','test_cancellation_recovery','test_growth_snapshot','test_host_remediation','test_disabled_host_package','-q'],capture_output=True,text=True,encoding='utf-8',timeout=180,env=dict(os.environ,PYTHONUTF8='1'))
dump(out/'TEST_RESULT.json',dict(source_commit=PIN,returncode=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),stdout=result.stdout,stderr=result.stderr,independent_review='PENDING',full_regression='NOT_RUN_FOR_THIS_PIN'))
assert result.returncode==0,result.stderr
print(json.dumps(dict(files=files,test_result=result.stderr,manifest_files=len(manifest)),ensure_ascii=False))
