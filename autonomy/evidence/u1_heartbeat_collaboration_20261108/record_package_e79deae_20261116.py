import copy,datetime,os,pathlib,sys,tempfile
r=pathlib.Path(r'D:\CODEX\roktandrazo-workspace\roktandrazo-outreach-autonomy');sys.path.insert(0,str(r))
from autonomy.supervisor import atomic_json,exclusive,read
rt=r/'autonomy/runtime';qp=rt/'queue.json';pp=r/'autonomy/AUTONOMOUS_TASK_QUEUE.json';cp=r/'autonomy/evidence/unattended_20261026/U1_CURRENT_CHECKPOINT.md';sp=r/'autonomy/evidence/unattended_20261026/U1_DELIVERY_STATUS.md';rp=r/'autonomy/evidence/u1_heartbeat_collaboration_20261108/REPORT_MANUAL_20261116T061755Z.md';key='u1_package_e79deae_20261116'
v=read(r/'u1-verify-e79deae-20261116.json')
assert v['source_commit']=='e79deae6402a21b84a9bdbc1f44418c4db08cc1c' and v['outcome']=='VERIFIED' and len(v['phases'])==6 and len(v['checks'])==4 and all(x['outcome']=='PASSED' for x in v['phases']+v['checks'])
assert v['manifest_files']==5059 and v['rollback_host_files']==4960 and v['rollback_host_and_tool_parity_verified'] is True and v['isolated_pointer_rollback_verified'] is True
assert v['archive_sha256']=='f1dcd2be27737779e9ec9069dcee7f9e57d86ed43d995d8d288f6200fcf53e2a' and v['rollback_archive_sha256']=='d5d55c9db3113a284b3a318a2e72ca5f2fcaad5ea9da4775af21c5d2d8727406'
assert v['installation_verified'] is False and v['rollback_verified'] is False and v['production_ready'] is False
when=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
rec={'recorded_at':when,'source_sha':v['source_commit'],'package_build':'PASS per builder; 5059 files','install_sha256':v['archive_sha256'],'rollback_sha256':v['rollback_archive_sha256'],'offline_verification':'VERIFIED six phases and four probes; 4960 Host parity and isolated pointer fixture','verification_run':'45d64562-61c6-4f56-b6bd-111611220012','independent_package_review':'PENDING','formal_installation':'UNKNOWN','production_acceptance':'UNKNOWN','delivery_state':'unchanged','BUSINESS_GROWTH':'UNKNOWN'}
s='''## 最新离线包与周期记录 / Current offline package and cycle record

固定源码 e79deae6402a21b84a9bdbc1f44418c4db08cc1c 的禁用离线包已构建，包含 5059 个文件。安装包 SHA256 f1dcd2be27737779e9ec9069dcee7f9e57d86ed43d995d8d288f6200fcf53e2a；回滚包 SHA256 d5d55c9db3113a284b3a318a2e72ca5f2fcaad5ea9da4775af21c5d2d8727406。已读取回执：受控运行 45d64562-61c6-4f56-b6bd-111611220012 结果 VERIFIED，六阶段、四探针、4960 个 Host 文件一致性及隔离指针夹具通过；运行 ID 据构建方回报。包独立审核 PENDING；正式安装、正式回滚和生产验收未证明。

Disabled offline package for e79deae contains 5059 files. Receipt confirms VERIFIED across six phases and four probes, 4960 Host file parity and the isolated pointer fixture; run ID is reported by the builder. Independent package review is PENDING; formal installation, rollback and production acceptance remain unproven. Delivery gates remain unchanged and business growth is UNKNOWN.

记录截止 / Record cutoff: '''+when+'''. 此时间为记录完成时间，主控周期的实际结束时间待主控记录。 / This is the record completion time; the controller records the actual cycle end.

'''
def put(path,data):
 fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
with exclusive(rt):
 q=read(qp);p=read(pp)
 if not isinstance(q,dict) or not isinstance(p,dict) or key in q or key in p:raise RuntimeError('invalid input or duplicate')
 oq=copy.deepcopy(q);op=copy.deepcopy(p);old={x:x.read_bytes() for x in (cp,sp,rp)}
 q[key]=rec;p[key]=rec;atomic_json(qp,q);atomic_json(pp,p)
 for path in old:put(path,s.encode()+old[path])
 a=read(qp);b=read(pp);assert a.pop(key)==rec and a==oq and b.pop(key)==rec and b==op
 assert all(x.read_bytes()==s.encode()+old[x] for x in old)
 print('PASS: queues, report and checkpoints verified; prior tasks preserved; record cutoff',when)
