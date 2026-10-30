# U1固定候选整体独立代码审核 / Independent review of the pinned U1 candidate

## 结论与精确范围 / Verdict and exact scope

中文：独立Reviewer已审阅固定源码 `d7d424c120281981e70753ea1c15fe130134929f` 的U1完整离线功能关联及本轮最终差异。`OFFLINE_CODE_REVIEW_PASSED=true`；这是离线源码审核结论，**不是生产批准、实机安装通过、无人登录运行通过或整体U1完成**。`U1_PRODUCTION_APPROVAL=NOT_APPROVED_FOR_PRODUCTION`，`PRODUCTION_INSTALLABLE=false`，`PRODUCTION_ACCEPTED=false`。源码/测试工作树对该固定提交无差异；报告由独立于这两条实现工作线的Reviewer撰写，没有修改实现代码或提交。

English: The independent reviewer inspected the complete offline U1 interactions and final changes at `d7d424c120281981e70753ea1c15fe130134929f`. `OFFLINE_CODE_REVIEW_PASSED=true` applies to source review only, **not production approval, live installation, unattended operation or completion of U1**. `U1_PRODUCTION_APPROVAL=NOT_APPROVED_FOR_PRODUCTION`, `PRODUCTION_INSTALLABLE=false`, and `PRODUCTION_ACCEPTED=false`. Reviewed source/tests have no working-tree differences from the pin. This reviewer is independent of both implementation workstreams and changed no implementation or commits.

## 实际审阅清单 / Files actually reviewed

- `autonomy/durable_slots.py`, `growth_ledger.py`, `growth_snapshot.py`, `ledger_evidence.py`, `single_slot_adapter.py`。
- `autonomy/cancellation_terminal.py`, `cancellation_terminal_bundle.py`, `cancellation_recovery.py`, `owner_drain_preflight.py`, `drain_bundle_preflight.py`, `lock_recovery.py`。
- `autonomy/host_preparation.py`, `host_remediation.py`, `release_contract.py`, `rollback_admission.py`, `bridge_acceptance.py`, `bridge_session_evidence.py`, `windows_observation.py`, `unattended_policy.py`。
- `autonomy/disabled_host_package.py`, `build_dev_disabled_host.py`, `windows/RoktU1Bridge.cs`, `windows/Install-DisabledHost.ps1`, `windows/Rollback-DisabledHost.ps1`。
- `autonomy/config/u1_host_disabled.xml`：旧禁用任务提案无trigger、placeholder身份/路径，不是本次SCM安装对象。 / The older disabled task proposal has no trigger and placeholder identity/paths; it is not an installation target of this SCM package.

中文：共25份源码/脚本/配置，包含历史导入在 `GrowthLedger.import_history` 的实际实现；不存在独立的 `growth_history_contract.py`，审核使用真实代码而非模块名推测。并审阅取消恢复、adapter、锁、安装包、历史导入、快照、回滚与发布合同的相关测试及本轮范围冻结报告。没有把旧局部审核PASS直接继承为新候选结论。

English: These25 source/script/configuration files include the actual history-import implementation in `GrowthLedger.import_history`; there is no separate `growth_history_contract.py`. The review uses real implementation rather than presumed module names. Associated recovery, adapter, lock, packaging, history, snapshot, rollback and release tests and the scope-freeze report were also read. Earlier scoped PASS verdicts were not inherited as the new candidate's verdict.

## 审核发现及关闭 / Findings and closure

1. 中文：普通 `SingleSlotAdapter.reconcile` 原先在费用超支时仍关闭栅栏；相同超支回执再次结算会返回DUPLICATE，也可能错误关闭。最终修复为先持久设置unverified，并要求结算结果为SETTLED/DUPLICATE且数据库实际state为settled，才verified_closed。独立测试覆盖首次OVERRUN与重复回执，保留锁且后端只调用一次。 / English: Ordinary reconciliation previously closed the fence on cost overrun; a duplicate overrun receipt could also return DUPLICATE and incorrectly close it. The final fix persists unverified first and requires both an acceptable result and actual persisted settled state before closure. Independent tests cover original/duplicate overrun receipts, retained locks and a single backend call.
2. 中文：取消恢复未重新检查当前对象路径，可能用指向A的签名事实对B副本操作。最终入口重新核对runtime/target/slot/budget路径身份和runtime目录inode，拒绝改变的目标；亦直接绑定原锁token及初始非恢复锁的历史进程身份。对应副本替换、锁身份替换负例独立通过。 / English: Recovery initially did not recheck current target objects, allowing signed facts for A to act on a B copy. It now checks runtime/target/slot/budget path identities and runtime inode, rejects substituted targets, and directly binds the original lock token and original process identity. Independent target-copy/lock-substitution negative tests pass.

中文：复核上述修复后，没有发现需要在此固定离线候选封版前继续修复的阻断性源码问题。尚未验证的生产事实不作为已关闭问题，见后述门禁。

English: After rechecking these fixes, no remaining blocking source defect was identified for this pinned offline candidate. Unverified production facts remain open gates below rather than resolved findings.

## 独立实测 / Independent executed tests

- `python -X utf8 -B -m unittest test_disabled_host_package test_growth_snapshot test_growth_history_contract test_rollback_admission test_release_contract -q`：33项通过，1.393秒。 /33 passed in1.393s.
- `python -X utf8 -B -m unittest test_cancellation_recovery test_single_slot_adapter autonomy.test_lock_recovery -q`：52项通过，15.884秒。 /52 passed in15.884s.

中文：合计85项独立定向测试通过。包含真实Windows C#编译/禁用配置CLI、PowerShell语法解析、真实子进程退出与重新打开SQLite、guard四进程初始化、活进程拒绝、未知schema/签名/回执冲突、恢复权限拒绝派发，以及普通超支/重复超支栅栏。没有运行安装/回滚脚本的Execute分支。833项可比全量由主线另行执行，以本轮固定提交的实际失败/错误ID比较报告为准；独立85项通过不能替代该比较，也不能宣称全量全绿。

English: A total of85 independent targeted tests passed, including real Windows C# compilation/disabled-config CLI, PowerShell parsing, process exits/SQLite reopen, four-process guard initialization, live-owner rejection, schema/signature/receipt conflicts, recovery-only dispatch denial and ordinary/duplicate overrun fencing. Installer/rollback Execute branches were not run. The main workstream runs the833-test comparable suite separately; its actual failure/error-ID comparison for this pin governs regression claims. These85 passes neither replace that comparison nor establish an all-green full suite.

中文：独立重新从Git读取全部25个blob，逐项核对 `SOURCE_MANIFEST.json` 的blob ID、SHA256、字节数及 `PINNED_SOURCE.zip` 对应内容，25/25一致。独立核对重新构建开发包全部7份artifact/script哈希和大小，并核对C#及两安装/回滚脚本等于固定Git字节；包manifest SHA256=`1011e76faa2bedf793991f0860d87cc53e2f49d3a0af76cf49b4391bc7e4a3c0`，source_commit精确为本次候选。已读 `PINNED_IMPORT.json` 的21模块隔离导入成功记录及本地Python/SQLite/时区观察，后两者是主线执行证据，不虚称本Reviewer另行重复执行。包仍明确allow_install=false/production_ready=false。

English: All25 blobs were independently reread from Git and checked against manifest blob IDs, SHA256, byte counts and ZIP contents:25/25 match. All seven rebuilt package artifact/script hashes and sizes were independently checked, including exact pinned Git bytes for C# and both installer/rollback scripts. Package manifest SHA256 is `1011e76faa2bedf793991f0860d87cc53e2f49d3a0af76cf49b4391bc7e4a3c0` and source_commit exactly matches this candidate. The21-module isolated-import success record and local Python/SQLite/timezone observations were read as main-workstream evidence, not misrepresented as independent reruns. The package explicitly retains allow_install=false/production_ready=false.

## 持久恢复、兼容与回滚 / Durable recovery, compatibility and rollback

中文：跨库顺序为固定证据PREPARED日志→slot终态→独立取消费用→原预算→COMPLETED日志→verified_closed。原取消意图日志保持不可变；丢确认、部分提交与退出不自动重放、不自动退款。恢复专用身份在既有adapter和reserve_then_claim入口硬拒绝派发，原owner存活或身份不确定不接管。guard通过完整marker原子发布后使用OS锁，进程退出释放内核锁；旧空guard不删除、不猜测陈旧。旧O_EXCL执行器遇到新marker会失败关闭，**不能回滚后直接启动旧执行器**。正式迁移/回滚必须停派发、排空/对账、验证新旧执行器与当前账本和guard合同，保留所有claim、UNKNOWN、预算、历史、取消与恢复日志；不得恢复旧数据库覆盖事实。

English: Cross-store order is fixed-evidence PREPARED journal, slot terminal, independent cancellation cost, original budget, COMPLETED journal, then verified_closed. Original cancellation intent remains immutable. Lost acknowledgements, partial commits and exits never authorize replay or refunds. Recovery-only contexts are denied dispatch by adapter and reserve_then_claim; live or uncertain owners cannot be adopted. A complete guard marker is atomically published before OS locking, allowing process-exit release; legacy empty guards are neither deleted nor presumed stale. Legacy O_EXCL executors fail closed on the new marker: **rollback cannot simply restart an old executor**. Formal migration/rollback must stop dispatch, drain/reconcile, verify executor/current-ledger/guard compatibility and preserve claims, UNKNOWN, budgets, history, cancellation and recovery journals. Never restore an old database over recorded facts.

## Windows与生产未验收门禁 / Windows and production gates not accepted

中文：安装工具和开发包可构建，默认预检，明确Execute+管理员及精确清单哈希才可能创建指定新服务；默认Disabled，不自动启动，虚拟服务身份非LocalSystem，代码RX/状态Modify，回滚仅撤销匹配且已停服务登记并保留代码和状态。当前未执行安装、ACL/身份变更、启用或回滚；有效ACL、服务登录权、SCM行为与真实依赖仍需正式实机验证。脚本局部安装互斥不能代替原Inventory/正式发布器的维护窗口和唯一调度权威。

English: The installer and development package can be built. Installation defaults to preflight; only explicit Execute, administrator context and exact manifest hash may register the specified new Disabled service. No automatic start occurs; it uses a virtual service identity rather than LocalSystem, code RX/state Modify, and rollback removes only a matching stopped registration while retaining code/state. No installation, identity/ACL change, activation or rollback was executed. Effective ACLs, service-logon rights, SCM behavior and real dependencies need formal live validation. The local install mutex cannot replace the original Inventory/publisher maintenance window and sole scheduling authority.

中文：新C#宿主仅本地无签名heartbeat，无8791监听器、Python执行器、生产backend或调度器；它**不满足**既有 `host_remediation.CONFIG` 的8791认证health/reconcile、Python runtime与31门禁。六份.NET直接依赖观察不证明Windows/.NET全部传递依赖闭包。正式Python/SQLite/时区、发布器新增文件/备份/原子替换/删除回滚、生产信任根、7877之外非交互出口、跨登录/无人登录及两次原Inventory自然周期仍待WorkBuddy正式证据。新服务只是默认禁用安装候选，不是业务执行接入已完成。

English: The new C# host only writes local unsigned heartbeat; it has no8791 listener, Python executor, production backend or scheduler. It **does not satisfy** existing host_remediation.CONFIG requirements for authenticated8791 health/reconcile, Python runtime and31 gates. Six observed direct .NET dependencies do not prove the complete Windows/.NET transitive closure. Production Python/SQLite/timezone, publisher new-file/backup/atomic-replacement/removal rollback, trust roots, approved noninteractive egress beyond7877, cross-login/login-free behavior and two original-Inventory cycles still require formal WorkBuddy evidence. This is a disabled installation candidate, not completed business-execution integration.

## 下一步与自检 / Next steps and self-check

中文：主线完成固定候选清单、可比回归、开发包重建与推送核对后，通过既有GitHub通道提交本候选的P1兼容验证；不重复旧消费回执或合同请求。只有实机门禁及可审核窗口明确后才提出一次性最小管理员授权。SMTP保持关闭，未访问生产数据库或运行采集，未创建第二Inventory，当前SAFE及业务增长UNKNOWN。报告自检通过：双语、实际数量/结果/风险/未执行/下一步齐全，无凭据、客户资料、代理地址或原始token。

English: After the main workstream pins the manifest, completes comparable regression/rebuild/push verification, submit this candidate's P1 compatibility check through the existing GitHub channel without repeating old acknowledgements/contracts. Request one bounded administrator approval only after live gates and a reviewable window are defined. SMTP remains off; no production database access, collection or second Inventory occurred. Current SAFE/growth remain UNKNOWN. Report self-check passes: bilingual, with actual counts/results/risks/non-actions/next steps and no credentials, customer data, proxy addresses or raw tokens.

中文：另独立审阅 `CONTROLLED_RELEASE_AND_ROLLBACK.md`：精确范围、原Inventory/发布器互斥、默认禁用且不启动的授权草案、账本/guard保留及旧执行器不得复启的回滚门禁与源码一致。`ROLLBACK_PLAN_REVIEW_PASSED=true`仅表示该停止并保留方案可审，不表示实机回滚演练或执行授权。没有将局部安装互斥误作生产运行锁，也没有把启动/权威切换暗含于禁用登记。

English: `CONTROLLED_RELEASE_AND_ROLLBACK.md` was independently reviewed: exact scope, original-Inventory/publisher exclusion, disabled/no-start authorization draft and ledger/guard preservation with no legacy-executor restart match the code. `ROLLBACK_PLAN_REVIEW_PASSED=true` approves review of this stop-and-preserve plan only, not a live rollback drill or execution authority. It neither substitutes installation exclusion for the production run lock nor embeds activation/cutover into disabled registration.

## Git运输封存复核 / Git transport seal recheck

中文：独立从运输提交 `c7f2ac15391f3fe3522d3e218650749474b39188` 的Git对象读取包清单、全部5份文件与2份脚本和ZIP，未依赖工作树内容。此前被忽略的 `runtime/build.json` 与 `runtime/dependencies.json` 现已纳入Git；7份artifact/script的SHA256与字节数全部匹配清单，ZIP加上manifest共8个条目，条目集合精确一致且每份字节等于Git对象，未发现依赖文件遗漏。`.gitattributes` 将该开发包目录设为 `-text`，防止运输时文本换行转换。功能源码仍固定为 `d7d424c120281981e70753ea1c15fe130134929f`，本次未重复功能测试。

English: The manifest, all five files plus two scripts, and ZIP were independently read from Git objects at transport commit `c7f2ac15391f3fe3522d3e218650749474b39188`, without relying on working-tree content. Previously ignored `runtime/build.json` and `runtime/dependencies.json` are now tracked. All seven artifact/script SHA256 values and byte counts match the manifest. The ZIP contains exactly those seven entries plus the manifest, with every entry byte-identical to Git; no declared dependency file is omitted. `.gitattributes` marks this development-package directory `-text` to prevent newline conversion in transport. Functional source remains pinned to `d7d424c120281981e70753ea1c15fe130134929f`; no functional tests were repeated for this transport-only change.

中文：包manifest SHA256为 `1011e76faa2bedf793991f0860d87cc53e2f49d3a0af76cf49b4391bc7e4a3c0`；ZIP为12297字节，SHA256为 `2575e0d0c4a1ea19f1267e691d9e8323acc57e0418787661b0699f91a910fd95`，与 `DEV_PACKAGE_TRANSPORT.json` 一致。`TRANSPORT_REVIEW_PASSED=true`。此结果仅证明固定开发包可完整运输，`production_approved=false`及上述生产未批准结论保持不变。

English: Manifest SHA256 is `1011e76faa2bedf793991f0860d87cc53e2f49d3a0af76cf49b4391bc7e4a3c0`. ZIP size is12297 bytes and SHA256 is `2575e0d0c4a1ea19f1267e691d9e8323acc57e0418787661b0699f91a910fd95`, matching `DEV_PACKAGE_TRANSPORT.json`. `TRANSPORT_REVIEW_PASSED=true`. This establishes complete transport of the fixed development package only; `production_approved=false` and the production non-approval above remain unchanged.
