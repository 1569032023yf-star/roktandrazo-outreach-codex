"""回滚包逐文件对应，不执行回滚 / Rollback archive parity, no rollback execution."""
from pathlib import Path
import hashlib,json,zipfile
root=Path(r"C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-config-ec45401")
build=json.loads((root/'BUILD.json').read_text())
archive=root/'rollback-tools.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==build['artifacts'][archive.name]
count=0
with zipfile.ZipFile(archive) as rollback, zipfile.ZipFile(root/'install.zip') as install:
 manifest=json.loads(install.read('manifest.json'))
 for name in rollback.namelist():
  if name.startswith('host/') and not name.endswith('/'):
   raw=rollback.read(name)
   assert raw==install.read('payload/'+name),name
   assert hashlib.sha256(raw).hexdigest()==manifest['files'][name],name
   count+=1
 for name,target in {'release_store.py':'python/autonomy/release_store.py','OFFLINE-DELIVERY.md':'README.md','dependencies/business-wheels.lock.json':'dependencies/business-wheels.lock.json','dependencies/cpython-input.lock.json':'dependencies/cpython-input.lock.json'}.items():
  raw=rollback.read(name)
  assert raw==install.read('payload/'+target),name
  assert hashlib.sha256(raw).hexdigest()==manifest['files'][target],name
  count+=1
report=dict(outcome='VERIFIED',source_commit=build['source_commit'],archive_sha256=build['artifacts'][archive.name],matched_components=count,rollback_archive_parity_verified=True,rollback_verified=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,description_zh='仅回滚包逐文件对应，不代表实际安装或回滚。',description_en='Rollback archive parity only; not actual installation or rollback.')
(Path(__file__).parent/'ROLLBACK_PARITY.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(report))
