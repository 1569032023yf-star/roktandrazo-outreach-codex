"""Assemble reviewed source without deploying / 组装审核源码，不执行部署。"""
import hashlib,json,subprocess,sys,tempfile,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
SOURCE='d47e5d9f2f51bf0acc2f9dc4d3dc2a12b6287923'
def blob(name):return subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def main():
 folder=HERE/'channel-package';folder.mkdir()
 binding=json.loads(blob('publisher_channel/CHANNEL_SOURCE_BINDING.json'))
 old={row['name']:row['original_sha256'] for row in binding['files']}
 mapping={f'bin/{name}':f'publisher_channel/{name}' for name in ('bridge.py','executor.py','registry.py','multifile.py','prodobs.py')}
 for name in ('install_admission','install_command','install_inputs','install_maintenance','install_process','install_verifier'):
  mapping[f'publisher_channel/{name}.py']=f'publisher_channel/{name}.py'
 for name in ('directory_identity','disabled_host_package','host_file_transaction','inventory_maintenance','process_control','process_job'):
  mapping[f'autonomy/{name}.py']=f'autonomy/{name}.py'
 rows=[]
 for target,source in sorted(mapping.items()):
  raw=blob(source);path=folder/'payload'/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
  rows.append(dict(target=target,source=source,sha256=digest(raw),bytes=len(raw),
   expected_before=dict(kind='FILE',sha256=old[target[4:]]) if target.startswith('bin/') else dict(kind='ABSENT')))
 for name in ('ORIGINAL_INVENTORY_ADMISSION.patch','COMPANION_BINDING.json'):
  (folder/name).write_bytes(blob('autonomy/evidence/u1_inventory_fence_20261103/'+name))
 manifest=dict(schema='rokt.u1-publisher-support.v1',source_commit=SOURCE,files=rows,
  required_atomic_rollout=['original Inventory admission companion','original Publisher admission','trusted configuration approval and seal refresh'],
  installable_release=False,automatic_update_supported=False,production_applied=False,
  allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
 (folder/'manifest.json').write_bytes(canonical(manifest))
 (folder/'README.md').write_text('''# 原Publisher配套工程包 / Original Publisher support archive

这是固定源码的离线配套包，不含生产配置、凭据或自动更新器；未部署。bin路径对应既有原通道，新helper固定在原通道根目录的publisher_channel和autonomy。原通道Credential Manager身份验证与seal保留。每个原文件须精确匹配expected_before SHA，新文件目标必须ABSENT；已有未知文件不得覆盖。运行时仅限既有唯一Inventory，不创建调度器。
This fixed-source offline support archive contains no production configuration, credentials or automatic updater and is not deployed. bin paths correspond to the original channel; new helpers occupy fixed publisher_channel/autonomy directories at its root. Existing Credential Manager authentication and seal remain. Original files require exact expected_before hashes; new targets must be ABSENT. Unknown existing files must not be overwritten. Only the existing sole Inventory is used; no scheduler is created.

原Inventory补丁另附原始binding，仅供原执行权所有者正式通道审核发布，不纳入宿主文件白名单。必须同窗口完成原Inventory准入、Publisher准入、受信配置和seal更新，完整审核及授权前门禁全false。本包不是完整可安装发布版，不证明现场SCM/ACL或无人值守成功；禁止直接解压覆盖现场。
The original Inventory companion patch retains its original binding for reviewed release by the existing owner through the formal channel; it does not expand host-file targets. Original Inventory admission, Publisher admission and trusted configuration/seal updates require one controlled window. All gates remain false before complete review and authorization. This is not a complete installable release or proof of actual SCM/ACL/unattended success. Never extract it over the site.
''',encoding='utf-8')
 archive=HERE/'publisher-support.zip'
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
  for path in sorted(folder.rglob('*')):
   if path.is_file():z.write(path,path.relative_to(folder).as_posix())
 # Import the delivered layout in a fresh isolated interpreter: no main(),
 # config load, credential access, listener, service or database operation.
 with tempfile.TemporaryDirectory(prefix='u1-channel-package-') as temp:
  dest=Path(temp)
  with zipfile.ZipFile(archive) as z:z.extractall(dest)
  payload=dest/'payload'
  code="import sys;from pathlib import Path;r=Path(sys.argv[1]);sys.path[:0]=[str(r/'bin'),str(r)];import bridge;from publisher_channel import install_admission,install_command;assert bridge.CHANNEL_ROOT==r;assert install_command.RELEASES==r/'releases';assert '/v1/u1-install' in bridge.AUTH_POST;assert not list(r.rglob('*.db'));print('DELIVERED_IMPORT_ONLY_OK')"
  run=subprocess.run([sys.executable,'-I','-B','-c',code,str(payload)],cwd=dest,capture_output=True,text=True,timeout=20)
  if run.returncode!=0:raise ValueError('DELIVERED_IMPORT_FAILED: '+run.stderr)
 result=dict(source_commit=SOURCE,artifact_sha256=digest(archive.read_bytes()),manifest_sha256=digest((folder/'manifest.json').read_bytes()),
  payload_files=len(rows),import_only_passed=True,import_output=run.stdout.strip(),production_applied=False,installable_release=False)
 (HERE/'CHANNEL_PACKAGE.json').write_bytes(canonical(result));print(json.dumps(result))

if __name__=='__main__':main()
