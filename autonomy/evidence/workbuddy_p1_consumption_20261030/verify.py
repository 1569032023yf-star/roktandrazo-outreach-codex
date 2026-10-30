"""固定交接重验 / Reverify pinned Git bytes and declared evidence structures."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
receipt=json.loads((root/'CONSUMPTION_RECEIPT.json').read_text(encoding='utf-8'))
required={
 'U1_P1_COMPAT_EVIDENCE_20261030.json':{'schema','generated_at','producer','scope','pinned_inputs','package_integrity','items','summary','safety_attestation','evidence_files_sha256'},
 'U1_ROLLBACK_ADMISSION_20261030.json':{'schema','source','inventory_id','cases','assertions','dispatch_ever_allowed','all_assertions_pass'},
 'U1_V2_GUARD_MATRIX_20261030.json':{'schema','source','sandbox_root','marker_expected','cases','pass','fail'}}
for row in receipt['files']:
 raw=(root/'source'/row['name']).read_bytes()
 assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['git_blob_sha']
 assert hashlib.sha256(raw).hexdigest()==row['sha256']
 if row['name'] in required:
  d=json.loads(raw);assert type(d) is dict and required[row['name']]<=d.keys()
  if 'items' in d:
   assert [x['id'] for x in d['items']]==[1,2,3,4,5]
   assert all(type(x['sub_results']) is list and x['sampled_at'] for x in d['items'])
  if 'assertions' in d:
   assert len(d['assertions'])==8 and all(v is True for v in d['assertions'].values())
   assert d['dispatch_ever_allowed'] is False
  if 'marker_expected' in d:
   assert d['marker_expected']=='rokt.recovery-guard.v2\n'
   assert len(d['cases'])==11 and d['pass']==10 and d['fail']==0
 else:assert raw.decode('utf-8').strip()
print('4 Git blobs/3 declared JSON structures/1 document verified; not production acceptance')
