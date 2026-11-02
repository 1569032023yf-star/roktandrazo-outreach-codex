"""Package hash/PE/import verification / 包哈希、PE 与实际模块验证。"""
from pathlib import Path
import hashlib,json,struct,zipfile,subprocess,sys,time
out=Path(sys.argv[1]);pkg=out/'package';bundle=pkg/'install'
m=json.loads((bundle/'manifest.json').read_bytes());files=m['files'];verified={}
for name,expected in files.items():
 raw=(bundle/'payload'/name).read_bytes();actual=hashlib.sha256(raw).hexdigest();assert actual==expected,name;verified[name]=actual
assert {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}=={'manifest.json'}|{'payload/'+n for n in files}
host=bundle/'payload/host';hm=json.loads((host/'manifest.json').read_bytes())
for f in hm['files']+hm['scripts']:
 raw=(host/f['path']).read_bytes();assert len(raw)==f['size'] and hashlib.sha256(raw).hexdigest()==f['sha256'],f['path']
exe=(host/'service/RoktU1Bridge.exe').read_bytes();offset=struct.unpack_from('<I',exe,0x3c)[0];machine=struct.unpack_from('<H',exe,offset+4)[0];assert exe[offset:offset+4]==b'PE\0\0' and machine==0x8664
artifacts={}
for label in ('install','rollback-tools'):
 folder=pkg/label;zpath=pkg/(label+'.zip')
 with zipfile.ZipFile(zpath) as z:
  expected={p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()};assert set(z.namelist())==set(expected)
  for n,b in expected.items():assert z.read(n)==b,n
 artifacts[zpath.name]=hashlib.sha256(zpath.read_bytes()).hexdigest()
value=dict(description_zh='固定候选安装包逐文件、归档及真实AMD64检查；未执行安装。',description_en='Pinned package file/archive and real AMD64 verification; no installation.',source_commit=m['source_commit'],manifest_sha256=hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest(),host_manifest_sha256=hashlib.sha256((host/'manifest.json').read_bytes()).hexdigest(),pe_machine=hex(machine),all_files_verified=verified,artifacts=artifacts,allow_dispatch=False,allow_cancel_dispatch=False,service_installed=False)
(out/'PACKAGE_VALIDATION.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in value.items() if k!='all_files_verified'}))
code="import sys,unittest; from pathlib import Path; sys.path[:0]="+repr([str((bundle/'payload/python').resolve()),str(Path.cwd())])+"; import autonomy.host_file_transaction as f,autonomy.inventory_event_bridge as e; assert Path(f.__file__).is_relative_to("+repr(str((bundle/'payload/python').resolve()))+"); print(f.__file__); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(['test_host_file_transaction','test_inventory_event_bridge'])); sys.exit(not r.wasSuccessful())"
start=time.monotonic();r=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
(out/'PACKAGED_TEST_OUTPUT.txt').write_text(r.stdout+r.stderr,encoding='utf-8');(out/'PACKAGED_TEST.json').write_text(json.dumps(dict(source_commit=m['source_commit'],returncode=r.returncode,seconds=round(time.monotonic()-start,3),modules=['test_host_file_transaction','test_inventory_event_bridge'],import_root=str((bundle/'payload/python').resolve()),passed=r.returncode==0),indent=2),encoding='utf-8');print('packaged_tests_returncode',r.returncode)
sys.exit(r.returncode)
