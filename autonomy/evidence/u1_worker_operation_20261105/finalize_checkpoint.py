"""同步本轮固定证据 / Synchronize fixed cycle evidence."""
import json,hashlib,zipfile
from pathlib import Path
from datetime import datetime,timezone
r=Path.cwd();e=Path(__file__).resolve().parent
source='6de5cf3d421e0073be905a57e0dd3cd2cc1024a6'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
baseline=r/'autonomy/evidence/u1_provider_worker_20261105/clean-candidate-suite/result.json';candidate=e/'clean-candidate-suite/result.json'
b=read(baseline);c=read(candidate)
comp=dict(source_commit=source,baseline_source_commit='9d5ecb6b8062f916ac7869957eb6589665ce9113',baseline_result_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),candidate_result_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),candidate_run=c['run'],failures=len(c['failures']),errors=len(c['errors']))
for k in ('failures','errors'):
 comp['new_'+k+'_ids']=sorted(set(c[k])-set(b[k]));comp['resolved_'+k+'_ids']=sorted(set(b[k])-set(c[k]))
write(e/'REGRESSION_COMPARISON.json',comp)
build=read(e/'BUILD.json');verify=read(e/'EXTRACTED_REPORT.json');probe=read(e/'PACKAGED_WORKER_REPORT.json')
assert build['source_commit']==source and verify['source_commit']==source and verify['outcome']!='RUNNING'
p=r.parent/'u1-delivery-operation-6de5cf3'
with zipfile.ZipFile(p/'install.zip') as a,zipfile.ZipFile(p/'rollback-tools.zip') as z:
 host={n[len('payload/'):]:hashlib.sha256(a.read(n)).hexdigest() for n in a.namelist() if n.startswith('payload/host/') and not n.endswith('/')}
 rollback={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('host/') and not n.endswith('/')}
 mismatches=sorted(k for k in set(host)|set(rollback) if host.get(k)!=rollback.get(k))
parity=dict(outcome='PASSED' if not mismatches else 'FAILED',host_files=len(host),rollback_files=len(rollback),mismatches=mismatches,actual_rollback=False)
write(e/'ROLLBACK_PARITY.json',parity)
now=datetime.now(timezone.utc).isoformat();cp=(e/'REPORT.md').relative_to(r).as_posix()
statuses={k:False for k in ('DEVELOPMENT_COMPLETE','RELEASE_READY','PRODUCTION_DEPLOYED','PRODUCTION_ACCEPTED')};statuses['BUSINESS_GROWTH']='UNKNOWN'
zh='继续原Owner绑定的业务请求映射和权威回执接线；缺失费用、终态、幂等及取消合同不得执行外部请求或伪造回执。'
en='Continue original-owner-bound business request mapping and authoritative receipt wiring; missing cost, terminal, idempotency and cancellation contracts prohibit external requests or fabricated receipts.'
state=dict(updated_at=now,source_commit=source,checkpoint=cp,targeted_tests=dict(run=24,failures=0,errors=0),full_regression=comp,package=build,extracted_verification=verify['outcome'],packaged_worker_probe=probe,rollback_component_parity=parity,rollback_verified=False,independent_review='PENDING',formal_backend_integrated=False,provider_contract='CONTRACT_MISSING',statuses=statuses,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,next_action=en)
write(e/'STATUS.json',state)
report=f"""# U1 Worker操作绑定接线 / Worker operation binding

固定源码 / Fixed source: {source}
时间 / Time: {now}

中文：正式Worker执行入口现在消费后端stdin操作，限制65536字节，拒绝重复JSON键、非有限数值、错误协议、Inventory、执行范围及幂等摘要。原事件或claim摘要出现时必须完整绑定锁、运行身份、账本及claim，并核对token摘要关联。无效操作在构造真实适配器前拒绝且不回显输入。此为完整性校验，父ProcessBackend仍负责Owner活性授权；不把摘要校验当作独立授权。
English: The real Worker entrypoint now consumes backend stdin, limits input to65536 bytes and rejects duplicate JSON keys, nonfinite values, invalid protocol/Inventory/scope and idempotency digests. Original event or claim digests require complete lock, identity, ledger and claim joins, including token-digest consistency. Invalid operations fail before adapter construction without echoing input. This validates integrity; the parent ProcessBackend remains responsible for live owner authority.

中文：24项定向测试通过；新固定源码隔离全量{comp['candidate_run']}项，{comp['failures']}FAIL/{comp['errors']}ERROR；新增失败ID {comp['new_failures_ids']}，新增错误ID {comp['new_errors_ids']}。基线9d5ecb6实测记录与候选记录SHA均保存，不继承旧833结果，不声称全绿。
English:24 targeted tests pass. The clean fixed-source full suite runs{comp['candidate_run']} tests with{comp['failures']} failures/{comp['errors']} errors; added failure IDs {comp['new_failures_ids']}, added error IDs {comp['new_errors_ids']}. Measured9d5ecb6 baseline and candidate result hashes are recorded. No old833-result inheritance or all-green claim.

中文：新AMD64禁用包{build['files']}文件，固定CPython及业务依赖；实际解压核验{verify['outcome']}，实际包内Worker操作输入探针{probe['outcome']}，回滚组件对应{parity['outcome']}（{parity['host_files']}文件）。组件对应不等于现场备份或实际回滚。未安装、未启用服务、未触发Inventory、未发信、未写生产数据库。
English: New disabled AMD64 archive contains{build['files']} files with pinned CPython and business dependencies. Actual extraction verification:{verify['outcome']}; actual packaged Worker operation probe:{probe['outcome']}; rollback component parity:{parity['outcome']} ({parity['host_files']} files). Component parity is not a site backup or actual rollback. No installation, service activation, Inventory trigger, email or production database write occurred.

Install SHA256: {build['artifacts']['install.zip']}
Rollback tools SHA256: {build['artifacts']['rollback-tools.zip']}
Manifest SHA256: {build['manifest_sha256']}

中文：默认执行仍CONTRACT_MISSING/exit78，不调用外部服务、不签终态或计费回执；后端UNKNOWN不重放。缺少operation/run/claim权威绑定、终态、幂等保证、取消费用回执、账单账户/project/SKU、使用量周期/数量/单位、金额/币种/credits及账单证据引用；browser_maps另缺来源授权和请求回执。内部命名不构成阻塞。独审PENDING，真实业务执行闭环及Windows安装/启动/注销/跨登录验收未完成。全部最终状态false，BUSINESS_GROWTH=UNKNOWN；安装/派发/取消/SMTP门禁false。
English: Default execution remains CONTRACT_MISSING/exit78 without external requests or terminal/billing receipts; backend UNKNOWN is never replayed. Missing authoritative operation/run/claim binding, terminal status, idempotency guarantee, cancellation-fee receipts, billing account/project/SKU, usage period/quantity/unit, amount/currency/credits and billing evidence reference; browser_maps additionally lacks source authorization and request receipts. Internal naming is not a blocker. Independent review PENDING; real business closure and Windows install/start/logoff/across-login acceptance remain incomplete. All final states false, BUSINESS_GROWTH UNKNOWN; install/dispatch/cancel/SMTP gates false.

中文：本轮实际05:51:28启动，06:36:28截止；平台无整轮硬超时字段，子进程有界，最多两条重型工作线。保留历史锁及他人文件。未执行生产安装或实际回滚，未伪造Reviewer通过。
English: Actual cycle05:51:28 to06:36:28; no platform whole-turn hard-timeout field, individually bounded subprocesses and at most two heavy workstreams. Historical locks and other work are preserved. No production installation/actual rollback or fabricated Reviewer approval.

下一动作 / Next action: {zh}
{en}

自检 / Self-check: 中英双语、计数、风险、未执行项及下一步齐备，无凭据或伪完成。 Bilingual, counts, risks, omissions and next action recorded; no credentials or false completion.
"""
(e/'REPORT.md').write_text(report,encoding='utf-8')
for path in (r/'autonomy/runtime/queue.json',r/'autonomy/AUTONOMOUS_TASK_QUEUE.json'):
 q=read(path);q.update(updated_at=now,checkpoint=cp,u1_worker_operation_latest=state,u1_continuous_development_current=state,u1_cycle_boundary=dict(actual_started_at='2026-11-05T05:51:28+08:00',stop_before='2026-11-05T06:36:28+08:00',state='CHECKPOINTED',work_stopped_at=now,platform_hard_timeout_available=False,max_heavy_workstreams=2))
 t=next(t for t in q['tasks'] if t['id']=='A-unattended-architecture-20261026');t.update(updated_at=now,checkpoint=cp,candidate_commit=source,review_status='PENDING',next_action=en,next_action_zh=zh,next_action_en=en,u1_worker_operation_latest=state,targeted_tests=state['targeted_tests'],full_regression=comp,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
 write(path,q)
summary=f'中文：固定{source}接入有界Worker操作解析和原claim摘要绑定，24项定向通过；全量{comp["candidate_run"]}项{comp["failures"]}FAIL/{comp["errors"]}ERROR，见ID对比。新禁用包解压{verify["outcome"]}，包内操作探针{probe["outcome"]}。独审/正式业务闭环PENDING，全部最终状态及门禁false，BUSINESS_GROWTH=UNKNOWN。见{cp}。\nEnglish: Fixed{source} wires bounded Worker operation parsing and original-claim digest binding;24 targeted pass, full{comp["candidate_run"]} with{comp["failures"]} failures/{comp["errors"]} errors per ID comparison. Disabled archive extraction{verify["outcome"]}, packaged operation probe{probe["outcome"]}. Review/business closure PENDING, final states/gates false, BUSINESS_GROWTH UNKNOWN. See{cp}.\n\n'
for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
 p=r/'autonomy/evidence/unattended_20261026'/name;p.write_text(summary+p.read_text(encoding='utf-8'),encoding='utf-8')
print(cp)
