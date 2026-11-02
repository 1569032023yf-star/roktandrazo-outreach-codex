import importlib.util,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
out=Path(__file__).resolve().parent
package=out/'package/install'
payload=package/'payload/python'
sys.path.insert(0,str(payload))
from autonomy.release_store import ReleaseStore
assert Path(sys.modules['autonomy.release_store'].__file__).is_relative_to(payload)
manifest=json.loads((out/'package/BUILD.json').read_text(encoding='utf-8'))
spec=importlib.util.spec_from_file_location('packaged_bootstrap',package/'payload/host/service/u1_bootstrap.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)
with tempfile.TemporaryDirectory(prefix='u1-pkg-') as temp:
 root=Path(temp);store=ReleaseStore(root)
 version=store.stage(package,manifest['manifest_sha256'])
 receipt=store.activate(version,expected_current=None)
 assert bootstrap.resolve_release(root)==root/'versions'/version/'payload/python'
 store.rollback(receipt['transaction'],expected_current=version)
 assert store.status()['version'] is None
 code="""import os,sys
sys.path.insert(0,sys.argv[1])
from autonomy.release_store import ReleaseStore
real=os.replace
def crash(*args):
 real(*args)
 os._exit(27)
os.replace=crash
ReleaseStore(sys.argv[2]).activate(sys.argv[3],expected_current=None)
"""
 result=subprocess.run([sys.executable,'-I','-B','-c',code,str(payload),str(root),version],timeout=20)
 assert result.returncode==27
 state=store.recovery_status()
 assert state['pending'][0]['pointer_relation']=='TARGET_CURRENT'
 try:bootstrap.resolve_release(root)
 except ValueError as exc:assert 'STOP_AND_PRESERVE' in str(exc)
 else:raise AssertionError('uncertain release booted')
 try:store.rollback(receipt['transaction'],expected_current=version)
 except ValueError as exc:assert 'STOP_AND_PRESERVE' in str(exc)
 else:raise AssertionError('uncertain rollback replayed')
 summary=dict(source_commit=manifest['source_commit'],manifest_sha256=version,
  package_module_loaded=True,stage_activate_verified=True,rollback_to_absent_verified=True,
  child_exit_code=27,unknown_after_real_commit=True,bootstrap_blocked=True,
  rollback_replay_blocked=True,production_action=False)
(out/'PACKAGE_EXERCISE.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary))
