"""同步真实固定候选证据 / Synchronize actual fixed candidate evidence."""
import json
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd();e=Path(__file__).resolve().parent
source='69eb1887800f046b6d860cbefad6bd99f3c35169'
now=datetime.now(timezone.utc).isoformat();checkpoint=(e/'REPORT.md').relative_to(root).as_posix()
build=json.loads((e/'BUILD.json').read_text());extracted=json.loads((e/'EXTRACTED_REPORT.json').read_text());probe=json.loads((e/'PACKAGED_BINDING_REPORT.json').read_text());rollback=json.loads((e/'ROLLBACK_PARITY.json').read_text());regression=json.loads((e/'REGRESSION_COMPARISON.json').read_text())
assert all(d['source_commit']==source for d in (build,probe,rollback))
assert extracted['outcome']=='UNKNOWN' and probe['returncode']==0 and rollback['outcome']=='VERIFIED'
statuses={k:False for k in ('DEVELOPMENT_COMPLETE','PACKAGE_COMPLETE','PROVIDER_ACCEPTED','WINDOWS_ACCEPTED','RELEASE_READY','PRODUCTION_DEPLOYED','PRODUCTION_ACCEPTED')};statuses['BUSINESS_GROWTH']='UNKNOWN'
next_en='Connect the approved Provider reference pair through the original owner-controlled ProcessBackend/Worker launch, retaining isolated_offline and closed production gates; authoritative settlement remains CONTRACT_MISSING.'
next_zh='将批准Provider路径/摘要对接入原Owner控制的ProcessBackend/业务Worker启动；保留isolated_offline与生产门禁关闭，权威结算仍CONTRACT_MISSING。'
record=dict(updated_at=now,source_commit=source,checkpoint=checkpoint,targeted_tests=dict(run=42,failures=0,errors=0,log=(e/'TARGETED.txt').relative_to(root).as_posix()),full_regression=regression,package=build,extracted_verification='UNKNOWN_TIMEOUT_FINAL_INTEGRITY',packaged_reference_probe='PASS',rollback_matched_components=rollback['matched_components'],rollback_verified=False,independent_review='PENDING',host_configuration_propagation='INSTALL_PLAN_TO_HOST_LIFETIME_PIN_VERIFIED',worker_configuration_propagation='NOT_IMPLEMENTED',package_verification_recovery='Inspect preserved extracted tree and verifier final revalidation performance; do not claim VERIFIED or replay installation',provider_contract='CONTRACT_MISSING',statuses=statuses,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,next_action=next_en)
text=fr"""# U1 安装与宿主接线 / Installation and host wiring

时间 / Time: {now}
固定源码 / Fixed source: {source}

中文：实际安装计划新增成对Provider配置绝对路径/批准SHA256，经生成runtime.json、bootstrap参数进入宿主。安装器与宿主使用Windows输入固定；宿主持有配置和祖先句柄直至退出，验证失败在快照/owner/监听前拒绝；不把密钥写入runtime.json、服务环境或HTTP。原业务Worker尚未接收该配置，不声称自动执行已完成。
English: Paired absolute Provider configuration path/approved SHA256 now flows from the actual installation plan through generated runtime.json and bootstrap into the host. Installer and host use Windows input pins; the host holds file/ancestor handles until exit and rejects invalid input before snapshot/owner/listener access. Credentials are not written to runtime.json, service environment or HTTP. The original business Worker does not yet receive this reference; automatic execution is not claimed complete.

中文：修复真实Publisher安装验收仍用Base64读取外置块字典以及512文件上限两个P0阻断。复用文件事务decoder核查固定operation日志旁的块存储身份和内容SHA，不添加任意路径或重放能力；上限与8192包文件加2生成配置一致。42项定向组合全部通过，包括真实临时文件首装、升级、两类回滚及块篡改后保留UNKNOWN维护锁。SCM/ACL为隔离替身，不能替代Windows安装验收。
English: Repairs two P0 Publisher acceptance blockers: decoding actual blob references as Base64 and a512-file limit. Reuses the transaction decoder to verify sibling blob-store identity/content hashes for the fixed operation journal; no arbitrary path or replay support is added. Capacity matches8192 package files plus2 generated configs. All42 targeted combined checks pass, covering real temporary file first-install, upgrade, both rollbacks and UNKNOWN maintenance retention after blob tampering. SCM/ACL are isolated substitutes, not Windows installation acceptance.

中文：干净固定候选tests/实际848项，37FAIL/17ERROR与同日干净ec45401固定结果ID一致，无新增，不是全绿；固定基线原始结果路径及SHA256见REGRESSION_COMPARISON.json，没有机械重跑未变基线。旧13f989d组合23项4 ERROR已保留说明，不能把修复前失败隐藏为通过。
English: The actual clean fixed tests/ candidate runs848 tests with37 failures/17 errors, matching same-day clean ec45401 fixed result IDs without additions; not fully passing. REGRESSION_COMPARISON.json records the reused fixed baseline path/SHA256; the unchanged baseline is not mechanically rerun. The earlier23-test13f989d combination had4 errors and remains documented rather than rewritten as success.

中文：真实AMD64禁用包{build['files']}文件，含固定CPython3.13.12及12个固定wheel。四项包内运行检查通过；最终完整性复核在600秒父进程硬超时后为UNKNOWN，未通过整体验证；另用真实包内CPython验证配置终身写保护、bootstrap参数和实际完整宿主清单容量。回滚{rollback['matched_components']}组件逐文件对应通过，不是现场备份或真实回滚。未安装或启用任何服务，未触发Inventory/Provider/邮件。
English: The actual AMD64 disabled archive contains{build['files']} files, pinned CPython3.13.12 and12 locked wheels. Four packaged runtime checks pass; final integrity revalidation is UNKNOWN after the parent600-second hard timeout. Overall verification has not passed. A separate actual packaged-CPython probe checks lifetime write protection, bootstrap arguments and real complete host-manifest capacity. All{rollback['matched_components']} rollback components match; this is neither a site backup nor actual rollback. No service was installed/enabled and no Inventory/Provider/email operation was triggered.

安装包 / Install archive: C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-host-69eb188\install.zip
SHA256: {build['artifacts']['install.zip']}
回滚工具 / Rollback tools: C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-host-69eb188\rollback-tools.zip
SHA256: {build['artifacts']['rollback-tools.zip']}
Manifest SHA256: {build['manifest_sha256']}

中文：独立审核PENDING；权威费用/真实终态回执CONTRACT_MISSING；原Worker闭包、真实7877/8791跨登录及Windows安装/开机/Session0/恢复验收未完成。所有最终状态false，BUSINESS_GROWTH=UNKNOWN；allow_install/allow_dispatch/allow_cancel_dispatch/SMTP=false。没有新的需用户决定的内部命名事项。整轮无平台硬超时字段，不宣称强制45分钟；包核验子进程600秒硬时限。
English: Independent review PENDING; authoritative charges/real terminal receipts CONTRACT_MISSING. Original Worker closure, real7877/8791 across logins and Windows installation/boot/Session0/recovery acceptance remain incomplete. All final states false; BUSINESS_GROWTH UNKNOWN and all four safety gates false. No internal-naming decision is required from the user. No platform whole-turn hard-timeout field is available; a forced45-minute limit is not claimed. The package-verification subprocess has a600-second hard limit.

开发下一动作 / Next development action:
{next_zh}
{next_en}
"""
(e/'REPORT.md').write_text(text,encoding='utf-8');(e/'STATUS.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for path in (root/'autonomy/runtime/queue.json',root/'autonomy/AUTONOMOUS_TASK_QUEUE.json'):
 q=json.loads(path.read_text(encoding='utf-8'));q.update(updated_at=now,checkpoint=checkpoint,u1_host_provider_binding_latest=record,u1_continuous_development_current=record)
 t=next(t for t in q['tasks'] if t['id']=='A-unattended-architecture-20261026')
 t.update(updated_at=now,checkpoint=checkpoint,candidate_commit=source,review_status='PENDING',next_action=next_en,next_action_zh=next_zh,next_action_en=next_en,u1_host_provider_binding_latest=record,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,smtp_enabled=False)
 path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=f'中文：固定{source}接通安装计划至宿主Provider引用/终身固定，修复Publisher外置块和完整包容量阻断。42项组合通过；干净tests/848项37FAIL/17ERROR与固定ec45401基线ID一致。新真实5056文件禁用包四项运行和包内接线探针通过；最终完整性复核600秒超时UNKNOWN，回滚4964组件对应通过。独审PENDING，Worker传播未实现，权威费用回执CONTRACT_MISSING；所有最终状态与安全门禁false，BUSINESS_GROWTH=UNKNOWN。详见{checkpoint}。\nEnglish: Fixed{source} wires Provider references from installation plan to host lifetime pins and repairs Publisher blob-backed/full-package acceptance.42 combination tests pass; clean tests/848 has matching37 failure/17 error IDs against fixed ec45401. New actual5056-file disabled archive passes four runtime checks and packaged wiring probe; final integrity is UNKNOWN after600-second timeout;4964 rollback components match. Review PENDING, Worker propagation unimplemented, authoritative cost/receipt contracts missing; all final states/gates false and BUSINESS_GROWTH UNKNOWN. See{checkpoint}.\n\n'
for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
 p=root/'autonomy/evidence/unattended_20261026'/name;p.write_text(summary+p.read_text(encoding='utf-8'),encoding='utf-8')
print(json.dumps({'source':source,'checkpoint':checkpoint,'synchronized':True}))
