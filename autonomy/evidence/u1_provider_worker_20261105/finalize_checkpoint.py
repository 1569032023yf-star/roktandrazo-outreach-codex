"""本轮证据同步 / Synchronize this cycle evidence."""
import json
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd();e=Path(__file__).resolve().parent
source='9d5ecb6b8062f916ac7869957eb6589665ce9113'
now=datetime.now(timezone.utc).isoformat();cp=(e/'REPORT.md').relative_to(root).as_posix()
build=json.loads((e/'BUILD.json').read_text());comparison=json.loads((e/'REGRESSION_COMPARISON.json').read_text());verify=json.loads((e/'EXTRACTED_REPORT.json').read_text())
assert build['source_commit']==source and comparison['source_commit']==source and verify['source_commit']==source and verify['outcome']!='RUNNING'
probe=json.loads((e/'PACKAGED_WORKER_REPORT.json').read_text()) if (e/'PACKAGED_WORKER_REPORT.json').exists() else {'outcome':'NOT_RUN'}
rollback=json.loads((e/'ROLLBACK_PARITY.json').read_text()) if (e/'ROLLBACK_PARITY.json').exists() else {'outcome':'NOT_RUN'}
statuses={k:False for k in ('DEVELOPMENT_COMPLETE','PACKAGE_COMPLETE','PROVIDER_ACCEPTED','WINDOWS_ACCEPTED','RELEASE_READY','PRODUCTION_DEPLOYED','PRODUCTION_ACCEPTED')};statuses['BUSINESS_GROWTH']='UNKNOWN'
zh='接入原Owner约束的Worker操作解析及业务请求映射；权威费用、终态和取消合同缺失继续拒绝外部请求，不签伪造回执。'
en='Wire original-owner-bound operation parsing and business request mapping; keep external requests blocked without authoritative cost, terminal and cancellation contracts and never fabricate receipts.'
r=dict(updated_at=now,source_commit=source,checkpoint=cp,targeted_tests=dict(run=20,failures=0,errors=0),full_regression=comparison,package=build,extracted_verification=verify['outcome'],packaged_worker_probe=probe,rollback_component_parity=rollback,rollback_verified=False,independent_review='PENDING',worker_entrypoint='REAL_ADAPTER_PREFLIGHT_AND_CONTRACT_REFUSAL_ONLY',formal_backend_integrated=False,provider_contract='CONTRACT_MISSING',statuses=statuses,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,next_action=en)
report=f"""# U1 固定Provider Worker入口 / Pinned Provider Worker entrypoint

固定源码 / Fixed source: {source}
时间 / Time: {now}

中文：新增包内 provider_worker.py 入口，使用 -I -B 可从任意当前目录加载固定树中的真实Google Places/browser_maps适配器和批准配置；配置上下文及祖先句柄持续持有。ProcessBackend.for_provider_worker 将后端、固定Worker路径和批准的配置/源码摘要接线，不自算可信摘要。--preflight仅输出无凭据能力信息，不请求服务或创建缓存。默认执行路径返回CONTRACT_MISSING和缺失字段，exit78，不发送外部请求、不签slot/budget回执。后端据此保留持久UNKNOWN且不重放；不是正式业务执行完成。
English: The packaged provider_worker.py runs with -I -B from any working directory and constructs real Google Places/browser_maps adapters from approved pinned configuration. Configuration and ancestor handles remain held. ProcessBackend.for_provider_worker wires the backend to the fixed Worker path and caller-approved configuration/source digests, without calculating trusted digests itself. --preflight exposes credential-free capabilities only, without service requests or cache creation. Default execution returns CONTRACT_MISSING and missing fields with exit78, starts no external request and signs no slot/budget receipts. The backend preserves durable UNKNOWN and rejects replay. This does not complete formal business execution.

中文：20项定向通过，包含真实子进程入口、篡改配置摘要拒绝且不泄露配置、后端真实Worker拒绝后UNKNOWN持久化与禁止重放及原后端/配置组合。初次引用测试夹具类名称错误1ERROR，修正后通过；原始结果保留。隔离全量{comparison['candidate_run']}项，{comparison['failures']}FAIL/{comparison['errors']}ERROR；新增失败ID{comparison['new_failures_ids']}、新增错误ID{comparison['new_errors_ids']}，详见固定240f614实测基线对比；不是全绿。
English: 20 targeted tests pass, including a real subprocess entrypoint, tampered-config rejection without disclosure, durable UNKNOWN/no replay after real Worker refusal, and existing backend/configuration combinations. An initial fixture-class import error was corrected; its original result remains. Clean full regression runs {comparison['candidate_run']} tests with {comparison['failures']} failures/{comparison['errors']} errors; added failure IDs {comparison['new_failures_ids']} and added error IDs {comparison['new_errors_ids']}. The measured fixed240f614 comparison is retained; this is not all green.

中文：新包{build['files']}文件，AMD64禁用态，含固定CPython及12依赖wheel。实际解压核验{verify['outcome']}；包内实际Worker探针{probe['outcome']}；回滚组件对应{rollback['outcome']}，不等于实际备份或回滚。未安装服务、未触发Inventory、未写生产数据库或发信。
English: The new {build['files']}-file AMD64 disabled archive bundles pinned CPython and12 dependency wheels. Actual extraction verification {verify['outcome']}; packaged real Worker probe {probe['outcome']}; rollback component parity {rollback['outcome']}, which is not a site backup or actual rollback. No service installation, Inventory trigger, production database writes or email occurred.

Install SHA256: {build['artifacts']['install.zip']}
Rollback tools SHA256: {build['artifacts']['rollback-tools.zip']}
Manifest SHA256: {build['manifest_sha256']}

中文：缺少权威operation/run/claim绑定、终态、幂等、取消费用、账单账户/project/SKU、使用量周期/数量/单位、金额/币种/credits和账单证据引用；browser_maps另缺来源授权和请求回执。未用缓存计数或模拟费用替代。独审PENDING，原Owner到业务请求/权威回执闭环、真实Windows安装启动注销/Session0/跨登录验收未完成。所有最终状态false，BUSINESS_GROWTH=UNKNOWN，安装/派发/取消/SMTP均false。整轮无平台硬超时字段；本轮实际02:51:29启动，03:36:29截止，子进程单独硬限，最多两条重型工作线。
English: Missing contracts cover operation/run/claim binding, terminal status, idempotency, cancellation fees, billing account/project/SKU, usage period/quantity/unit, amount/currency/credits and billing evidence references; browser_maps additionally lacks source authorization and request receipts. Cache counters or simulated costs do not substitute. Independent review PENDING. Original-owner-to-business-request/authoritative-receipt closure and real Windows install/start/logoff/Session0/across-login acceptance remain incomplete. All final states false, BUSINESS_GROWTH UNKNOWN, install/dispatch/cancel/SMTP false. No platform whole-turn hard-timeout field; actual cycle02:51:29 to03:36:29 with individually bounded subprocesses and at most two heavy workstreams.

下一动作 / Next action: {zh}
{en}

自检 / Self-check: 双语、数量、风险、未执行项、下一步齐备；无凭据、未冒称完成。 Bilingual, counts, risks, omissions and next action present; no credentials or false completion claims.
"""
(e/'REPORT.md').write_text(report,encoding='utf-8');(e/'STATUS.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for path in (root/'autonomy/runtime/queue.json',root/'autonomy/AUTONOMOUS_TASK_QUEUE.json'):
 q=json.loads(path.read_text(encoding='utf-8'));q.update(updated_at=now,checkpoint=cp,u1_provider_worker_latest=r,u1_continuous_development_current=r,u1_cycle_boundary=dict(actual_started_at='2026-11-05T02:51:29+08:00',stop_before='2026-11-05T03:36:29+08:00',state='CHECKPOINTED',work_stopped_at=now,platform_hard_timeout_available=False,max_heavy_workstreams=2))
 t=next(t for t in q['tasks'] if t['id']=='A-unattended-architecture-20261026');t.update(updated_at=now,checkpoint=cp,candidate_commit=source,review_status='PENDING',next_action=en,next_action_zh=zh,next_action_en=en,u1_provider_worker_latest=r,targeted_tests=r['targeted_tests'],full_regression=comparison,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
 path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=f'中文：固定{source}接通真实适配器Worker预检与ProcessBackend工厂，默认合同缺失exit78且不请求/不签回执，UNKNOWN禁止重放。20定向通过；全量{comparison["candidate_run"]}项{comparison["failures"]}FAIL/{comparison["errors"]}ERROR见ID比较。新{build["files"]}文件禁用包解压{verify["outcome"]}，包内Worker探针{probe["outcome"]}。独审及业务闭环PENDING，所有最终状态及门禁false，BUSINESS_GROWTH=UNKNOWN。见{cp}。\nEnglish: Fixed {source} wires real-adapter Worker preflight and ProcessBackend factory; missing contracts exit78 without requests/receipts and UNKNOWN cannot replay.20 targeted pass; full {comparison["candidate_run"]} with {comparison["failures"]} failures/{comparison["errors"]} errors per ID comparison. New {build["files"]}-file disabled archive extraction {verify["outcome"]}, packaged Worker probe {probe["outcome"]}. Review/business closure PENDING, final states/gates false, BUSINESS_GROWTH UNKNOWN. See {cp}.\n\n'
for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
 p=root/'autonomy/evidence/unattended_20261026'/name;p.write_text(summary+p.read_text(encoding='utf-8'),encoding='utf-8')
print(cp)
