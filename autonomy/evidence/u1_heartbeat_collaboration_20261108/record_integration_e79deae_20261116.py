import copy,datetime,os,pathlib,sys,tempfile
r=pathlib.Path(r'D:\CODEX\roktandrazo-workspace\roktandrazo-outreach-autonomy');sys.path.insert(0,str(r))
from autonomy.supervisor import atomic_json,exclusive,read
rt=r/'autonomy/runtime';qp=rt/'queue.json';pp=r/'autonomy/AUTONOMOUS_TASK_QUEUE.json';cp=r/'autonomy/evidence/unattended_20261026/U1_CURRENT_CHECKPOINT.md';sp=r/'autonomy/evidence/unattended_20261026/U1_DELIVERY_STATUS.md';rp=r/'autonomy/evidence/u1_heartbeat_collaboration_20261108/REPORT_MANUAL_20261116T061755Z.md';key='u1_integration_e79deae_20261116'
rec={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha':'e79deae6402a21b84a9bdbc1f44418c4db08cc1c','provider_candidate_sha':'90b05036fc7a896ac99566a8088bfaf7dfa7fa86','provider_independent_review':'PASS scoped','integrated':True,'integration_combined_test':'56/56 PASS run a27f1e45-5199-4b14-8df8-e491e7910a12','new_owner_two_settlements':'1/1 PASS on 90b per controller run d734d1bc-81e7-4878-b933-159d76d72f0d','existing_package_sha':'c724ad3e6bf2279cb6715aecaa19ed296a5492f7','final_package':'PENDING: rebuild and review required for e79deae','delivery_state':'unchanged','BUSINESS_GROWTH':'UNKNOWN'}
s='''## 集成修复与包版本 / Integrated fix and package version

Provider 修复 `90b05036fc7a896ac99566a8088bfaf7dfa7fa86` 经限定范围独立审核通过，已合并至固定源码 `e79deae6402a21b84a9bdbc1f44418c4db08cc1c`。该主线版本离线组合验证 56/56 通过（受控运行 `a27f1e45-5199-4b14-8df8-e491e7910a12`）。据主控回报，前次释放后新 owner 两次结算端到端测试在 90b 通过 1/1（受控运行 `d734d1bc-81e7-4878-b933-159d76d72f0d`）。

现存安装包仅绑定旧源码 `c724ad3e6bf2279cb6715aecaa19ed296a5492f7`，不可作为 e79deae 的最终交付包；新版包须重建并审核。开发、发布、生产部署和生产验收状态均不升级，业务增长 UNKNOWN；保留全部原有任务和门禁。

Provider fix 90b passed scoped independent review and was integrated into fixed source e79deae; 56/56 targeted integrated offline tests passed. Controller reports the new-owner two-settlement end-to-end test passed 1/1 against 90b. The existing package is bound only to c724ad3 and is not a final package for e79deae; rebuild and review remain pending. Development, release, production deployment and acceptance states are not promoted; business growth is UNKNOWN, and existing tasks and gates are preserved.

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
 print('PASS: queues read back; old fields and tasks preserved; report and checkpoints verified')
 for path in (qp,pp,cp,sp,rp):print(path)
