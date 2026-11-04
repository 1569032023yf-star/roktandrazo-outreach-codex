"""同步本轮实际证据 / Synchronize this cycle evidence."""
import json
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd();e=Path(__file__).resolve().parent
source='240f614fd694d48eb19edcfd8f8d3e187722875d'
now=datetime.now(timezone.utc).isoformat();cp=(e/'REPORT.md').relative_to(root).as_posix()
comparison=json.loads((e/'REGRESSION_COMPARISON.json').read_text())
build=json.loads((e/'BUILD.json').read_text()) if (e/'BUILD.json').exists() else None
verify=json.loads((e/'EXTRACTED_REPORT.json').read_text()) if (e/'EXTRACTED_REPORT.json').exists() else {'outcome':'NOT_RUN'}
assert verify['outcome']!='RUNNING'
statuses={k:False for k in ('DEVELOPMENT_COMPLETE','PACKAGE_COMPLETE','PROVIDER_ACCEPTED','WINDOWS_ACCEPTED','RELEASE_READY','PRODUCTION_DEPLOYED','PRODUCTION_ACCEPTED')};statuses['BUSINESS_GROWTH']='UNKNOWN'
next_zh='将批准配置适配器上下文接入原Owner控制的业务Worker入口，费用和终态合同缺失时继续拒绝正式结算。'
next_en='Wire the approved adapter context into the original owner-controlled business Worker; reject formal settlement without authoritative cost and terminal contracts.'
record=dict(updated_at=now,source_commit=source,checkpoint=cp,targeted_tests={'run':22,'failures':0,'errors':0},isolated_bridge_tests=7,isolated_owner_tests=12,combined_stage_bridge={'run':18,'errors':6,'reason':'DEVELOPMENT_EXTERNAL_TRANSPORT_DISABLED'},full_regression=comparison,package=build,extracted_verification=verify['outcome'],independent_review='PENDING',worker_entrypoint='PENDING',provider_contract='CONTRACT_MISSING',rollback_verified=False,rollback_matched_host_components=4960,statuses=statuses,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,next_action=next_en)
report=f"""# U1 执行文件固定修复 / Executable pinning fix

固定源码 / Fixed source: {source}
时间 / Time: {now}

中文：ProcessBackend 在写执行意图前固定 CPython 可执行文件和 Worker 源文件以及祖先路径句柄，持续持有到子进程清理和结果持久化结束，并在记录输出前重新核验。关闭构造后至启动前替换文件的竞态。复用安装器原生文件固定实现；不扩大为整个 DLL 或导入依赖闭包固定。未完成实际业务 Worker 接线。
English: ProcessBackend pins the CPython executable, Worker source and ancestor handles before execution intent, retains them through child cleanup/result persistence, and revalidates before recording output. This closes the file-replacement window after construction and before launch. Existing native installer pins are reused; this does not pin the complete DLL/import closure or complete business Worker wiring.

中文：22项定向通过，包含 Windows 句柄阻止写入/改名、意图前拒绝替换及原超时/UNKNOWN恢复。Bridge与Owner独立进程分别7项、12项通过。Stage和Bridge同进程组合18项有6ERROR，均为既有开发网络护栏拒绝；原始失败保留，未解除护栏，也不声明组合通过。初次测试类缩进错误已修正，首次失败记录保留。
English: 22 targeted tests pass, including Windows handle write/rename denial, pre-intent replacement rejection and existing timeout/UNKNOWN recovery. Separate Bridge and Owner processes pass 7 and 12 tests. The combined Stage/Bridge process has 6 errors in 18 tests, all rejected by the existing development transport guard. Raw failures are retained; the guard was not removed and this combination is not claimed passing. An initial test-class indentation error was corrected and its failure retained.

中文：固定候选隔离全量848项，37FAIL/17ERROR与实测594cd0a基线ID一致，无新增或消除ID；不是全绿。根目录定向不并入848。新包离线解压核验结果：{verify['outcome']}。5056文件AMD64包，含固定CPython和12个依赖wheel；4960个回滚host组件对应。构建和核验详情见同目录 BUILD.json、EXTRACTED_REPORT.json；只有 VERIFIED 才表示该离线核验通过。回滚组件对应不代表现场回滚。
English: The clean fixed candidate runs 848 tests with the same 37 failure and 17 error IDs as measured baseline 594cd0a; no IDs are added or resolved. This is not all green. Root-level targeted tests are separate from 848. New archive extraction verification: {verify['outcome']}. The 5056-file AMD64 archive bundles pinned CPython and 12 dependency wheels; 4960 rollback host components match. BUILD.json and EXTRACTED_REPORT.json record details; only VERIFIED establishes offline verification. Component parity does not establish a site rollback.

中文：独立审核 PENDING，真实 Worker、权威费用/终态/取消合同、Windows安装/启动/注销/Session0及跨登录验收仍未完成。未安装、未触发Inventory、未写生产DB、未发邮件。所有最终状态及门禁false，BUSINESS_GROWTH=UNKNOWN。整轮无平台硬超时字段；子进程有独立时限。
English: Independent review PENDING. Actual Worker wiring, authoritative cost/terminal/cancellation contracts, Windows install/start/logoff/Session0 and across-login acceptance remain incomplete. No installation, Inventory trigger, production database writes or email. All final states and gates remain false; BUSINESS_GROWTH UNKNOWN. No platform whole-turn hard-timeout field exists; subprocesses have individual limits.

安装包 / Install archive SHA256: {build['artifacts']['install.zip'] if build else 'UNKNOWN'}
回滚包 / Rollback tools SHA256: {build['artifacts']['rollback-tools.zip'] if build else 'UNKNOWN'}
Manifest SHA256: {build['manifest_sha256'] if build else 'UNKNOWN'}

下一动作 / Next action: {next_zh}
{next_en}

自检 / Self-check: 双语、数量及失败已明确；未执行项和风险已记录；无凭据。 Bilingual, counts and failures explicit; omissions/risks recorded; no credentials.
"""
(e/'REPORT.md').write_text(report,encoding='utf-8');(e/'STATUS.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for path in (root/'autonomy/runtime/queue.json',root/'autonomy/AUTONOMOUS_TASK_QUEUE.json'):
 q=json.loads(path.read_text(encoding='utf-8'));q.update(updated_at=now,checkpoint=cp,u1_executable_pins_latest=record,u1_continuous_development_current=record,u1_cycle_boundary=dict(actual_started_at='2026-11-04T23:53:18+08:00',stop_before='2026-11-05T00:38:18+08:00',state='CHECKPOINTED',work_stopped_at=now,platform_hard_timeout_available=False,max_heavy_workstreams=2))
 t=next(t for t in q['tasks'] if t['id']=='A-unattended-architecture-20261026');t.update(updated_at=now,checkpoint=cp,candidate_commit=source,review_status='PENDING',next_action=next_en,next_action_zh=next_zh,next_action_en=next_en,u1_executable_pins_latest=record,targeted_tests=record['targeted_tests'],full_regression=comparison,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
 path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=f'中文：固定{source}修复执行文件和Worker替换竞态，句柄持有到清理及持久化。22项定向通过，Bridge/Owner独立7/12通过；同进程18项6护栏ERROR保留。全量848项37FAIL/17ERROR与实测基线ID一致。新包解压核验{verify["outcome"]}，独审及Worker入口PENDING，所有最终状态和门禁false，BUSINESS_GROWTH=UNKNOWN。详见{cp}。\nEnglish: Fixed {source} pins executable/Worker through cleanup and persistence. 22 targeted pass; separate Bridge/Owner 7/12 pass; combined 18 retains 6 guard errors. Full 848 has unchanged 37 failure/17 error IDs. New archive verification {verify["outcome"]}; review/Worker PENDING; all final states/gates false, BUSINESS_GROWTH UNKNOWN. See {cp}.\n\n'
for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
 p=root/'autonomy/evidence/unattended_20261026'/name;p.write_text(summary+p.read_text(encoding='utf-8'),encoding='utf-8')
print(cp)
