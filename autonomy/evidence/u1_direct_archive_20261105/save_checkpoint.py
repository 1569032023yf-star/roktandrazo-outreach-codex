import json,datetime,subprocess
from pathlib import Path
r=Path.cwd();e=Path(__file__).parent;cp=e.relative_to(r).as_posix()+'/REPORT.md';now=datetime.datetime.now(datetime.timezone.utc).isoformat();source=subprocess.check_output(['git','rev-parse','fe51fbd^{commit}'],text=True).strip()
def read(p,default='PENDING'):
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
package=r.parent/'u1-delivery-direct-fe51fbd'
s=dict(updated_at=now,source_commit=source,checkpoint=cp,targeted_tests=dict(run=22,failures=0,errors=0,output='TARGETED.txt'),package=read(package/'BUILD.json','UNKNOWN_INCOMPLETE_BUILD'),partial_package=read(e/'PARTIAL_PACKAGE.json'),build_termination=read(e/'BUILD_TERMINATION.json'),regression=read(e/'COMPARISON.json'),extracted_verification=read(e/'EXTRACTED_REPORT.json'),independent_review='PENDING',provider_contract='CONTRACT_MISSING',allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,statuses={k:False for k in ['DEVELOPMENT_COMPLETE','PACKAGE_COMPLETE','PROVIDER_ACCEPTED','WINDOWS_ACCEPTED','RELEASE_READY','PRODUCTION_DEPLOYED','PRODUCTION_ACCEPTED']},next_action='Implement source-bound resumable build phases and phase timing:600-second build reached partial ZIP but not manifest completion; preserve partial ZIP and do not consume it as an install package. Then finish fixed-package verification and independent review.')
s['statuses']['BUSINESS_GROWTH']='UNKNOWN'
(e/'STATUS.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report="""# U1 直接归档构建修复 / Direct archive delivery fix

中文：固定源码%s将完整运行时载荷直接写入排他创建的install.zip，取消重复的逐文件持久化安装中间树。仍两次读取来源并逐文件核对SHA256、检查命名空间和大小上限，最后写manifest并flush/fsync。来源变化停止并保留失败归档，已有路径拒绝覆盖。回滚组件从安装归档精确字节提取。此改动仅构建，不安装或开启任何门禁。
English: Fixed source%s streams the complete runtime payload into exclusively created install.zip, eliminating the duplicate per-file durable staging tree. It retains two-pass source SHA256 checking, namespace/size limits, manifest completion and final flush/fsync. Changed sources stop and preserve the failed archive; existing paths cannot be overwritten. Rollback components consume exact archive bytes. This changes packaging only and opens no installation or dispatch gates.

中文：22项定向通过，覆盖来源变化、已有归档拒绝、manifest与归档对应、旧发布生命周期及传统工程包兼容性。真实构建600秒超时，只有部分ZIP，BUILD.json和完整回滚归档不存在；未启动独立解压核验。848项全量37FAIL/17ERROR与基线ID相同，无新增，但不是全绿。详见下列真实JSON；PENDING不能继承旧候选成绩。Windows实际安装、注销、Session0、业务回执和费用均未验收，独审PENDING。所有最终状态false；BUSINESS_GROWTH=UNKNOWN。
English:22 targeted checks pass, covering changed-source preservation, existing-archive refusal, manifest/payload parity, release lifecycle and legacy delivery compatibility. The actual build timed out at600 seconds with a partial ZIP; BUILD.json and a complete rollback archive are absent. Independent extraction was not started. The848 regression retains37 failures/17 errors with unchanged IDs; it is not green. Observed evidence follows; PENDING never inherits earlier candidate results. Real Windows installation, logout, Session0, business receipts and costs remain unaccepted; independent review is PENDING. All final statuses are false; BUSINESS_GROWTH is UNKNOWN.

中文：沿用09:35:30至10:20:30的本轮窗口，新构建子进程上限600秒；最多两条重型线。未配置平台整轮硬超时。此前900秒超时产物完整保留。
English: The cycle remains09:35:30–10:20:30, with a600-second bound for the new build and at most two heavy workstreams. No platform whole-cycle hard timeout is configured. Previous900-second partial outputs remain preserved.

```json
"""%(source,source)+json.dumps(s,ensure_ascii=False,indent=2)+'\n```\n'
(e/'REPORT.md').write_text(report,encoding='utf-8')
intro='中文：固定'+source+'直接归档构建修复；22定向通过，其余终态见'+cp+'。独审PENDING，所有最终状态/门禁false。\nEnglish: Fixed '+source+' direct-archive build fix;22 targeted pass. Outcomes: '+cp+'; review PENDING, final statuses/gates false.\n\n'
for name in ['U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md']:
 p=r/'autonomy/evidence/unattended_20261026'/name;p.write_text(intro+p.read_text(encoding='utf-8'),encoding='utf-8')
for name in ['autonomy/runtime/queue.json','autonomy/AUTONOMOUS_TASK_QUEUE.json']:
 p=r/name;q=read(p);q.update(updated_at=now,checkpoint=cp,u1_continuous_development_current=s,u1_direct_archive_latest=s);t=next(t for t in q['tasks'] if t['id']=='A-unattended-architecture-20261026');t.update(updated_at=now,checkpoint=cp,candidate_source_commit=source,u1_direct_archive_latest=s,next_action=s['next_action']);q['u1_cycle_boundary'].update(closed_at=now,checkpoint=cp);p.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(cp)
