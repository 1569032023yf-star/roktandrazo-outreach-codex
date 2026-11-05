import json,datetime,subprocess,hashlib
from pathlib import Path
r=Path.cwd();e=Path(__file__).parent;cp=e.relative_to(r).as_posix()+'/REPORT.md';now=datetime.datetime.now(datetime.timezone.utc).isoformat();source=subprocess.check_output(['git','rev-parse','3738993^{commit}'],text=True).strip()
def read(p,default='PENDING'):
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
base=r/'autonomy/evidence/u1_direct_archive_20261105/candidate-suite/result.json';candidate=e/'candidate-suite/result.json'
if candidate.exists():
 b=read(base);c=read(candidate);comparison=dict(source_commit=source,baseline_source_commit='fe51fbd05ed17eee727a25e2cd3a7b3430643249',run=c['run'],failures=len(c['failures']),errors=len(c['errors']),baseline_result_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),candidate_result_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
 for kind in ['failures','errors']:
  comparison['new_'+kind]=sorted(set(c[kind])-set(b[kind]));comparison['resolved_'+kind]=sorted(set(b[kind])-set(c[kind]))
 (e/'COMPARISON.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
package=r.parent/'u1-delivery-phased-3738993';prepared=r.parent/'u1-host-phase-3738993'
s=dict(updated_at=now,source_commit=source,checkpoint=cp,targeted_tests=dict(run=24,failures=0,errors=0,output='TARGETED.txt'),host_input=read(prepared/'HOST_INPUT.json'),prepare_termination=read(e/'PREPARE_TERMINATION.json'),package=read(package/'BUILD.json','UNKNOWN_INCOMPLETE_BUILD'),archive_termination=read(e/'ARCHIVE_TERMINATION.json'),regression=read(e/'COMPARISON.json'),extracted_verification=read(e/'EXTRACTED_REPORT.json'),verify_termination=read(e/'VERIFY_TERMINATION.json'),independent_review='PENDING',provider_contract='CONTRACT_MISSING',allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,statuses={k:False for k in ['DEVELOPMENT_COMPLETE','PACKAGE_COMPLETE','PROVIDER_ACCEPTED','WINDOWS_ACCEPTED','RELEASE_READY','PRODUCTION_DEPLOYED','PRODUCTION_ACCEPTED']},next_action='Use the existing prepared-host input handles for archive reads without repeated ancestor path queries, retaining per-file digest, identity and final revalidation. The900-second archive attempt is incomplete and must not be consumed. Then finish fixed-package extraction verification and independent review.')
s['statuses']['BUSINESS_GROWTH']='UNKNOWN'
(e/'STATUS.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report='''# U1 固定宿主分阶段交付构建 / Pinned host phased delivery build

中文：固定源码将宿主准备与归档拆分。准备阶段固定完整CPython、依赖及AMD64桥接，输出source/manifest绑定的HOST_INPUT；它不是完整安装包。归档入口对固定宿主持有输入句柄，核对runtime清单绑定，在最终身份复核后才写BUILD.json。失败归档保留，恢复使用新的排他输出，绝不覆盖或消费旧partial ZIP。24项定向通过。实际运行、回归、归档与独立解压结果逐项记录如下，PENDING/UNKNOWN不视为通过。独审PENDING，正式Provider费用/回执合同缺失，Windows安装/注销/Session0未验收。
English: Fixed source separates host preparation from archive assembly. Preparation pins complete CPython, dependencies and the AMD64 bridge and emits source/manifest-bound HOST_INPUT; this is not a complete installer. Archive assembly holds prepared-host input handles, checks runtime-manifest binding and writes BUILD.json only after final identity revalidation. Failed archives are preserved; recovery uses a new exclusive output without overwriting or consuming partial ZIPs.24 targeted tests pass. Actual phase, regression, archive and extraction outcomes are recorded below; PENDING/UNKNOWN is not a pass. Independent review remains PENDING; formal Provider cost/receipt contracts and actual Windows installation/logout/Session0 acceptance remain outstanding.

中文：本轮10:39:03至11:24:03 +08；子进程有显式时限，平台整轮硬超时未配置。未安装服务或改动生产，所有安装/派发/取消/SMTP门禁关闭；旧失败产物完整保留。
English: Cycle10:39:03–11:24:03 +08; subprocess timeouts are explicit, with no configured platform whole-cycle hard timeout. No service installation or production mutation; installation/dispatch/cancel/SMTP gates remain closed. Previous failed outputs remain preserved.

```json
'''+json.dumps(s,ensure_ascii=False,indent=2)+'\n```\n'
(e/'REPORT.md').write_text(report,encoding='utf-8')
intro='中文：固定'+source+'分阶段宿主/归档构建；24项定向通过。真实终态见'+cp+'。独审PENDING，最终状态与门禁false。\nEnglish: Fixed '+source+' phased host/archive build;24 targeted pass. Actual outcomes: '+cp+'; independent review PENDING, final statuses/gates false.\n\n'
for name in ['U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md']:
 p=r/'autonomy/evidence/unattended_20261026'/name;p.write_text(intro+p.read_text(encoding='utf-8'),encoding='utf-8')
for name in ['autonomy/runtime/queue.json','autonomy/AUTONOMOUS_TASK_QUEUE.json']:
 p=r/name;q=read(p);q.update(updated_at=now,checkpoint=cp,u1_continuous_development_current=s,u1_build_phases_latest=s);t=next(t for t in q['tasks'] if t['id']=='A-unattended-architecture-20261026');t.update(updated_at=now,checkpoint=cp,candidate_source_commit=source,u1_build_phases_latest=s,next_action=s['next_action']);q['u1_cycle_boundary'].update(closed_at=now,checkpoint=cp);p.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(cp)
