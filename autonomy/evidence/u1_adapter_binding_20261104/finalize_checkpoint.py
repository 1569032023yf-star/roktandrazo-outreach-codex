"""同步真实交付证据 / Synchronize actual delivery evidence."""
import json
from datetime import datetime, timezone
from pathlib import Path
root=Path.cwd();e=Path(__file__).resolve().parent
source='594cd0a513af461baac867a00e1f431339de3d7d'
now=datetime.now(timezone.utc).isoformat();checkpoint=(e/'REPORT.md').relative_to(root).as_posix()
build=json.loads((e/'BUILD.json').read_text());comparison=json.loads((e/'REGRESSION_COMPARISON.json').read_text());probe=json.loads((e/'PACKAGED_ADAPTER_REPORT.json').read_text());rollback=json.loads((e/'ROLLBACK_PARITY.json').read_text());extracted=json.loads((e/'EXTRACTED_REPORT.json').read_text())
assert all(x['source_commit']==source for x in (build,comparison,probe,rollback,extracted))
assert extracted['outcome']!='RUNNING'
statuses={k:False for k in ('DEVELOPMENT_COMPLETE','PACKAGE_COMPLETE','PROVIDER_ACCEPTED','WINDOWS_ACCEPTED','RELEASE_READY','PRODUCTION_DEPLOYED','PRODUCTION_ACCEPTED')};statuses['BUSINESS_GROWTH']='UNKNOWN'
next_zh='将批准配置适配器上下文接入原Owner控制的实际业务Worker入口，继续保持费用/终态合同缺失时拒绝正式结算及UNKNOWN不重放。'
next_en='Consume the approved-adapter context in the original owner-controlled business Worker entrypoint; reject formal settlement without authoritative cost/terminal contracts and never replay UNKNOWN.'
record=dict(updated_at=now,source_commit=source,checkpoint=checkpoint,targeted_tests=dict(run=27,failures=0,errors=0,log=(e/'TARGETED.txt').relative_to(root).as_posix()),full_regression=comparison,package=build,extracted_verification=extracted['outcome'],packaged_adapter_probe=probe,rollback_matched_host_components=rollback['matched_components'],rollback_verified=False,independent_review='PENDING',provider_contract='CONTRACT_MISSING',worker_entrypoint='PENDING',statuses=statuses,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,next_action=next_en)
text=fr"""# U1 Provider配置接线与真实安装包 / Provider configuration wiring and actual package

固定源码 / Fixed source: {source}
时间 / Time: {now}

中文：新增固定配置上下文到现有Google Places/browser_maps真实适配器的构造入口，不修改进程环境，不继承未批准的凭据、位置、direct模式或JSON输入。配置文件和祖先句柄持有至适配器上下文退出。修复browser_maps实例目录被全局CACHE_DIR覆盖的读写串用；构造不再创建缓存目录，仅实际保存结果时创建。复用原请求及认证实现，SerpAPI仍禁用。这不是业务Worker入口闭环或真实Provider验收。
English: A pinned configuration context now constructs existing real Google Places/browser_maps adapters without mutating process environment or inheriting unapproved credentials, locations, direct mode or JSON input. Configuration/ancestor handles remain pinned for the adapter context lifetime. Browser Maps reads/writes use the instance cache directory instead of the module-global directory; construction no longer creates a cache directory. Existing request/authentication implementations are reused; SerpAPI stays disabled. This does not complete the business Worker entrypoint or accept a live Provider.

中文：27项定向组合通过。首次27项中1个测试夹具缺少必填字段，修正夹具后通过，初始结果保留。新固定源码隔离全量848项，37FAIL/17ERROR与固定ec45401实测基线ID完全一致，新增失败/错误0；不是全绿。新根目录定向测试另行运行，不计入848项。基线与候选摘要和实际原始输出均保留。
English:27 targeted combination tests pass. The initial27-test run had one fixture missing required fields; the fixture was corrected and the initial result retained. A clean fixed-source full run executes848 tests with the same37 failure/17 error IDs as the measured ec45401 baseline, with zero added IDs; this is not an all-green suite. New root-level targeted tests run separately and are not counted in848. Digests and actual raw output are retained.

中文：已构建新5056文件AMD64禁用安装包，包含固定CPython和12个依赖wheel；包内真实CPython适配器探针通过，无网络请求、未安装服务。实际归档解压核验结果为{extracted['outcome']}，完成探针数{len(extracted.get('checks',[]))}；只有VERIFIED才代表该离线核验通过。回滚归档{rollback['matched_components']}个host组件逐文件对应，无差异；不是现场备份或实际回滚。构建先误用脚本路径入口，探针先误用运行时路径，均在启动前失败后修正，恢复记录保留。
English: A new5056-file AMD64 disabled install archive bundles pinned CPython and12 dependency wheels. The real packaged-CPython adapter probe passes without network requests or service installation. Actual extracted-archive verification outcome is{extracted['outcome']}, with{len(extracted.get('checks',[]))} completed probes; only VERIFIED establishes that offline verification. All{rollback['matched_components']} host components in the rollback archive match byte-for-byte; this is neither a site backup nor actual rollback. Initial script-entry and runtime-path invocation errors failed before launch and were corrected; recovery records are retained.

安装包 / Install archive: C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-adapter-594cd0a\install.zip
SHA256: {build['artifacts']['install.zip']}
回滚工具 / Rollback tools SHA256: {build['artifacts']['rollback-tools.zip']}
Manifest SHA256: {build['manifest_sha256']}

中文：独审PENDING；实际Worker接线、权威费用/终态/取消回执、真实Windows安装/启动/注销/Session0及7877/8791跨登录验收未完成。所有最终状态false，BUSINESS_GROWTH=UNKNOWN；allow_install/allow_dispatch/allow_cancel_dispatch/SMTP=false。没有改生产数据、触发Inventory或新增调度器。整轮无硬超时字段，不宣称强制45分钟；重型子进程有独立硬时限。
English: Independent review PENDING. Actual Worker wiring, authoritative cost/terminal/cancellation receipts, real Windows install/start/logoff/Session0 and7877/8791 across-login acceptance remain incomplete. All final states false, BUSINESS_GROWTH UNKNOWN and all four gates false. No production data changes, Inventory trigger or additional scheduler. The platform has no whole-turn hard-timeout field; a forced45-minute limit is not claimed. Heavy subprocesses have separate hard timeouts.

下一动作 / Next action:
{next_zh}
{next_en}
"""
(e/'REPORT.md').write_text(text,encoding='utf-8');(e/'STATUS.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for path in (root/'autonomy/runtime/queue.json',root/'autonomy/AUTONOMOUS_TASK_QUEUE.json'):
 q=json.loads(path.read_text(encoding='utf-8'));q.update(updated_at=now,checkpoint=checkpoint,remote_verified_head=source,remote_verified_commit=source,remote_verified=True,u1_adapter_binding_latest=record,u1_continuous_development_current=record,u1_cycle_boundary=dict(actual_started_at='2026-11-04T20:52:53+08:00',stop_before='2026-11-04T21:37:53+08:00',state='CHECKPOINTED',work_stopped_at=now,platform_hard_timeout_available=False,max_heavy_workstreams=2))
 t=next(t for t in q['tasks'] if t['id']=='A-unattended-architecture-20261026')
 t.update(updated_at=now,checkpoint=checkpoint,candidate_commit=source,review_status='PENDING',next_action=next_en,next_action_zh=next_zh,next_action_en=next_en,u1_adapter_binding_latest=record,targeted_tests=record['targeted_tests'],full_regression=comparison,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
 path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=f'中文：固定{source}接入批准配置真实适配器，修复browser_maps实例缓存串用和构造写目录。27项定向通过；隔离848项37FAIL/17ERROR与实测基线ID一致。新5056文件禁用包及包内适配器探针完成；解压核验{extracted["outcome"]}，回滚4960个host组件对应。独审PENDING、Worker入口PENDING、权威费用终态CONTRACT_MISSING；所有最终状态与门禁false，BUSINESS_GROWTH=UNKNOWN。详见{checkpoint}。\nEnglish: Fixed{source} constructs real adapters from approved configuration and fixes browser_maps instance cache leakage/construction writes.27 targeted pass; clean848 has identical37 failure/17 error IDs to measured baseline. New5056-file disabled archive and packaged adapter probe complete; extracted verification{extracted["outcome"]};4960 rollback host components match. Review/Worker entrypoint PENDING, authoritative cost/terminal contracts missing; all final states/gates false and BUSINESS_GROWTH UNKNOWN. See{checkpoint}.\n\n'
for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
 p=root/'autonomy/evidence/unattended_20261026'/name;p.write_text(summary+p.read_text(encoding='utf-8'),encoding='utf-8')
print(json.dumps({'synchronized':True,'checkpoint':checkpoint,'source':source}))
