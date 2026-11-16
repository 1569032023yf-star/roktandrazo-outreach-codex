import copy,datetime,os,pathlib,sys,tempfile
r=pathlib.Path(r'D:\CODEX\roktandrazo-workspace\roktandrazo-outreach-autonomy');sys.path.insert(0,str(r))
from autonomy.supervisor import atomic_json,exclusive,read
rt=r/'autonomy/runtime';qp=rt/'queue.json';pp=r/'autonomy/AUTONOMOUS_TASK_QUEUE.json';cp=r/'autonomy/evidence/unattended_20261026/U1_CURRENT_CHECKPOINT.md';sp=r/'autonomy/evidence/unattended_20261026/U1_DELIVERY_STATUS.md';rp=r/'autonomy/evidence/u1_heartbeat_collaboration_20261108/REPORT_MANUAL_20261116T061755Z.md';key='u1_manual_20261116T061755Z'
v=read(r/'u1-verify-c724ad3-20261116.json');assert v['source_commit']=='c724ad3e6bf2279cb6715aecaa19ed296a5492f7' and v['outcome']=='VERIFIED' and len(v['phases'])==6 and len(v['checks'])==4 and all(x['outcome']=='PASSED' for x in v['phases']+v['checks'])
rec={'task_id':'manual-20261116T061755Z','start':'2026-11-16T14:17:55+08:00','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'workdir':str(r),'start_sha':'9a98f67','integrated_sha':v['source_commit'],'provider_sha':'395533a16cfe7983c8cd7e6eb117e29e2f3f68b4','host_sha':'f9fe6e0e7fb7021b2d3d14153c0d8d1c9cf662ae','SCHEDULE_TRIGGERED':False,'C_EXECUTED':True,'AGENT_DELEGATED':True,'AGENT_RESULT_RECEIVED':True,'CODE_INTEGRATED':True,'source_push_and_reviews':'PASS per controller','integration_review':'PASS scoped','combined_tests':'93/93 PASS','main_code_pushed_verified':'PASS per controller','package':'offline six phases and four probes PASS; independent spot check PASS; full independent review PENDING','install_sha256':v['archive_sha256'],'rollback_sha256':v['rollback_archive_sha256'],'cross_database_host_concurrency_and_timeout':'UNKNOWN','delivery_state':'unchanged','BUSINESS_GROWTH':'UNKNOWN'}
s='''## 2026-11-16 手动开发轮次 / Manual development cycle

用户手动触发，开始 14:17:55 +08；主树起始版本 9a98f67，固定集成版本 c724ad3e6bf2279cb6715aecaa19ed296a5492f7。据主控回报，Provider 395533a 和 Host f9fe6e0 分支已推送核验并独审通过，主线代码已推送核验；固定集成独审及离线组合测试 93/93 通过。

离线禁用包验证回执六阶段与四探针通过，独立抽查通过，完整包独审仍 PENDING。安装包 SHA256 2477bcfb18b09eb6918eb0ef26b7bf8602b6db341edd7498c552ab83df46f445；回滚包 SHA256 4d36bc83386544839eef1026798018ee66e40f8bedbb1c44cac86db89ff499cb。该回执不证明正式安装、正式回滚或生产验收。跨库、跨主机并发及超时 UNKNOWN；开发、发布、生产部署与验收状态不升级，业务增长 UNKNOWN。

Manual trigger at 14:17:55 +08. Source branch push and reviews and main push are reported by the controller. Independent integration review and 93/93 offline combined tests passed on the fixed SHA. Offline receipt reports six phases and four probes passed; independent spot check passed and complete package independent review remains PENDING. The receipt does not establish formal installation, rollback or production acceptance. Cross-database and cross-host concurrency and timeout are UNKNOWN; delivery states remain unchanged and business growth is UNKNOWN.

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
 if not isinstance(q,dict) or not isinstance(p,dict) or key in q or key in p or rp.exists():raise RuntimeError('invalid input or duplicate record')
 oq=copy.deepcopy(q);op=copy.deepcopy(p);oc=cp.read_bytes();os_=sp.read_bytes()
 with rp.open('x',encoding='utf-8',newline='\n') as f:f.write('# 手动周期记录 / Manual cycle record\n\n'+s);f.flush();os.fsync(f.fileno())
 q[key]=rec;p[key]=rec;atomic_json(qp,q);atomic_json(pp,p);put(cp,s.encode()+oc);put(sp,s.encode()+os_)
 a=read(qp);b=read(pp);assert a.pop(key)==rec and a==oq and b.pop(key)==rec and b==op
 assert cp.read_bytes()==s.encode()+oc and sp.read_bytes()==s.encode()+os_ and rp.exists()
 print('PASS: queues read back; prior fields and task states preserved; checkpoint and report verified')
 for path in (qp,pp,cp,sp,rp):print(path)
