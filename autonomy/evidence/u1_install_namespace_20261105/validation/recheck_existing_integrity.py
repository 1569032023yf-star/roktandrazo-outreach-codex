"""现有包只读完整性复核 / Read-only integrity recheck; no probe inheritance."""
import hashlib,json,sys,time
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from autonomy.release_store import ReleaseStore
from publisher_channel.install_inputs import InstallInputPins,pin_package,pin_python_runtime
out=Path(__file__).with_name('EXISTING_INTEGRITY.json')
pkg=root.parent/'u1-delivery-search-21568c8'; extracted=root.parent/'u1-search-extracted-21568c8'
build=json.loads((pkg/'BUILD.json').read_text(encoding='utf-8'))
state=dict(package_source_commit=build['source_commit'],verifier_source_commit='1bf8d59aa1d9ce8ecb78da6590626bcf4380962f',outcome='RUNNING',checks=[],allow_install=False,allow_dispatch=False,smtp_enabled=False,package_complete=False,independent_review='PENDING',runtime_probes_repeated=False)
start=time.monotonic()
def checkpoint(phase):
 state.update(active_phase=phase,elapsed_seconds=round(time.monotonic()-start,3));out.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');print(phase,flush=True)
try:
 checkpoint('ARCHIVE_HASH')
 digest=hashlib.sha256()
 with (pkg/'install.zip').open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
 assert digest.hexdigest()==build['artifacts']['install.zip'],'ARCHIVE_HASH_MISMATCH'
 state['archive_sha256']=digest.hexdigest()
 checkpoint('OUTER_MANIFEST_AND_PAYLOAD')
 manifest=ReleaseStore(extracted)._verify(extracted,build['manifest_sha256'])
 assert manifest['source_commit']==build['source_commit']=='21568c8267d7d20b3127eab8d3f5c866202868fd'
 checkpoint('HOST_PIN_AND_RUNTIME')
 host=extracted/'payload/host';runtime=host/'runtime/python'
 with InstallInputPins() as pins:
  host_manifest=pin_package(pins,host,manifest['files']['host/manifest.json'],build['source_commit'])
  rows={row['path']:row['sha256'] for row in host_manifest['files']}
  pin_python_runtime(pins,str(runtime/'U1_RUNTIME_CONTENT.json'),rows['runtime/python/U1_RUNTIME_CONTENT.json'],str(runtime/'python.exe'))
  checkpoint('FINAL_PIN_REVALIDATION');pins.revalidate()
 checkpoint('FINAL_OUTER_REVALIDATION')
 ReleaseStore(extracted)._verify(extracted,build['manifest_sha256'])
 state.update(outcome='INTEGRITY_VERIFIED',manifest_files=len(manifest['files']),manifest_sha256=build['manifest_sha256'],description_zh='仅现有21568c8包完整性补充复核，不继承历史探针，不证明新源码包或安装验收。',description_en='Supplementary integrity recheck of existing21568c8 archive only; no historical probe inheritance, new-source package or installation acceptance.')
 checkpoint('COMPLETE')
except BaseException as exc:
 state.update(outcome='UNKNOWN' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'FAILED',error_type=type(exc).__name__,error=str(exc));checkpoint('STOP_AND_PRESERVE');raise
