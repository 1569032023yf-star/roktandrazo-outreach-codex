import copy, datetime, os, pathlib, sys, tempfile
r=pathlib.Path(r'D:\CODEX\roktandrazo-workspace\roktandrazo-outreach-autonomy'); sys.path.insert(0,str(r))
from autonomy.supervisor import atomic_json, exclusive, read
rt=r/'autonomy/runtime'; qp=rt/'queue.json'; pp=r/'autonomy/AUTONOMOUS_TASK_QUEUE.json'; cp=r/'autonomy/evidence/unattended_20261026/U1_CURRENT_CHECKPOINT.md'; sp=r/'autonomy/evidence/unattended_20261026/U1_DELIVERY_STATUS.md'; rp=r/'autonomy/evidence/u1_heartbeat_collaboration_20261108/REPORT_MANUAL_20261116T061755Z.md'; key='u1_review_e01c4c7_20261116'
rec={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha':'e01c4c7ed148661422447b38492cf59ca1c3387b','base_sha':'7e966d2','source_branch_pushed':'PASS per controller','independent_review':'FAIL: concurrent reconciliations can reopen a closed owner tree','integrated':False,'tests':'97 executed: 94 passed, 3 errors due to development_safety subprocess guard','host_offline_measurement':{'files':[10,20,40],'seconds':[5.195,11.055,20.538],'run_id':'45d64562-61c6-4f56-b6bd-111611220010','source':'host agent report; not root cause'},'delivery_state':'unchanged','BUSINESS_GROWTH':'UNKNOWN'}
s='''## 补充审核与测量 / Review and measurement update

Provider 候选代码 `e01c4c7ed148661422447b38492cf59ca1c3387b` 据主控回报已推送独立分支，独立审核未通过，未合并。两个并发对账可先后通过未闭合检查；第一个完成闭合后，第二个仍可能重新标记未验证，并在冲突或异常退出后保留错误状态。现有 owner 状态检查与状态转换未在同一事务完成。受控测试 97 项中 94 项通过，3 项因 development_safety 子进程限制报错，不能视为全绿。

Host 工作线报告小规模离线测量：10、20、40 个文件分别耗时 5.195、11.055、20.538 秒，受控运行 ID `45d64562-61c6-4f56-b6bd-111611220010`。这些测量尚不能确定启动超时根因。保留所有既有任务和生产门禁；开发、发布、部署及验收状态不升级，业务增长 UNKNOWN。

Provider candidate was pushed to its separate branch according to the controller; independent review failed and it was not merged. Concurrent reconciliation can check an open tree twice, then reopen an already closed owner tree; the check and transition are not atomic. Of 97 controlled tests, 94 passed and three errored because the development_safety subprocess guard blocked them. Host agent reports offline measurements of 5.195, 11.055 and 20.538 seconds for 10, 20 and 40 files respectively; these do not establish the startup-timeout root cause. Existing tasks, gates and delivery states remain unchanged; business growth is UNKNOWN.

'''
def put(path,data):
 fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
with exclusive(rt):
 q=read(qp); p=read(pp)
 if not isinstance(q,dict) or not isinstance(p,dict) or key in q or key in p: raise RuntimeError('invalid input or duplicate')
 oq=copy.deepcopy(q);op=copy.deepcopy(p);old={x:x.read_bytes() for x in (cp,sp,rp)}
 q[key]=rec;p[key]=rec;atomic_json(qp,q);atomic_json(pp,p)
 for path in (cp,sp,rp):put(path,s.encode()+old[path])
 a=read(qp);b=read(pp);assert a.pop(key)==rec and a==oq and b.pop(key)==rec and b==op
 assert all(x.read_bytes()==s.encode()+old[x] for x in old)
 print('PASS: canonical queue and projection read back with all prior fields and task states preserved; bilingual report and checkpoints verified')
 for path in (qp,pp,cp,sp,rp):print(path)
