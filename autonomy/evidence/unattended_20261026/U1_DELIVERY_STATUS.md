# U1 安装所有权修复 / Installation ownership repair

时间 / Time: 2026-11-02T08:49:26.631992+00:00
固定源码 / Fixed source: dcbddc3fe5535b39d789eba61df94f651aa2bd34

中文：安装器将所有权凭据从服务可修改的 ProgramData 移至代码目录 config/installation.json（预期服务只读）。使用 CreateNew、持久刷新及逐字节读回，拒绝覆盖。回滚读取凭据和执行文件时持有只读共享句柄，哈希基于该句柄读取的字节，直到回滚退出才释放。未修改生产服务、数据库、Inventory 或 SMTP。
English: The installer moves ownership evidence from service-writable ProgramData to config/installation.json in the code tree (intended read-only to the service). CreateNew, durable flush and byte readback refuse replacement. Rollback holds read-shared handles for the receipt and executable, hashes bytes read from those handles, and retains them until exit. No production service, database, Inventory or SMTP was changed.

验证 / Validation: python -B -m unittest test_u1_provision test_disabled_host_package -q — 8 PASS, 2.725s. 实际隔离文件验证凭据写入、拒绝覆盖、双文件写入封锁，以及 PowerShell 语法和真实 PE 编译。Actual isolated filesystem checks cover receipt creation, overwrite refusal and write blocking for both pinned files, plus PowerShell parsing and real PE compilation.

限制 / Limits: 此修复不证明实际 ACL 已验收，也不解决祖先目录/硬链接的全部竞争。旧 ProgramData 凭据不自动采纳。完整文件回滚、SCM 升级、宿主与原 Inventory 的执行接线仍未完成。新候选未重打安装包、未独审、未安装；旧包不得视为包含此修复。
This repair does not establish deployed ACL acceptance or eliminate every ancestor/hardlink race. Legacy ProgramData receipts are not automatically adopted. Full-file rollback, SCM upgrades and host execution wiring to the original Inventory remain incomplete. The new candidate has not been repackaged, independently reviewed or installed; old packages do not contain this fix.

下一步 / Next: 完成 SCM 升级与完整文件回滚，再冻结重打包并独审；继续原 Inventory 拥有者与执行宿主的接线，保持派发关闭。Finish SCM upgrade/full-file rollback, then freeze, rebuild packages and obtain independent review; continue existing Inventory-owner/host wiring with dispatch closed.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false

---

# U1执行接线与安装阻断修复 / U1 execution wiring and installation blocker fixes

更新时间 / Updated: 2026-11-02T08:40:48.546343+00:00
固定源码 / Pinned source: `cc9b7a7b672eb2098fa02d7e57c266b4ec57d76e`

实际代码 / Implemented code:
- ProcessBackend通过现有Job进程树运行固定哈希Python/worker；有界stdin传操作，不放入命令行。执行前提交IN_FLIGHT，进程中断、超时、丢失回执保留UNKNOWN；同identity不重放。正常返回仅缓存传输输出，现有SingleSlotAdapter仍验证签名和run/claim后才结算。
- ProcessBackend runs pinned Python/worker through the existing Job process tree, sending bounded stdin instead of operation-bearing argv. IN_FLIGHT commits before launch; crashes/timeouts/missing receipts remain UNKNOWN without replay. Cached output is transport evidence only; SingleSlotAdapter authenticates signed run/claim receipts before settlement.
- 原Inventory事件适配入口强制复用已持有的supervisor锁；不创建调度器或租约，不接受其他Inventory。新增只读恢复状态，不授予重放/退款/生产终态权限。
- Existing-Inventory event consumption requires the already-held supervisor lease. No new scheduler/lease, foreign Inventory, replay/refund or terminal authority is introduced.
- 安装器持有包清单、文件、配置计划与Python/token/snapshot依赖的只读句柄直至结束，实际测试写入被拒绝。修复最终SHA目录比暂存UUID目录更长造成的Windows路径故障，stage前预检最终布局。
- Installer pins manifest/artifacts/plan and Python/token/snapshot dependencies read-only through completion; mutation attempts were rejected in testing. Final SHA paths are now checked before staging, fixing the observed longer-final-directory Windows path failure.

验证 / Validation:
- 当前固定源码84项组合通过，47.799秒；包内实际模块5项通过，2.215秒。均为开发验证，不是独审。
- Current pinned source:84 combined tests passed in47.799s;5 tests loading the actual packaged module passed in2.215s. These are development checks, not independent review.
- 基线与本候选各833项，同37失败17错误，ID完全一致，新增失败/错误0，非全绿；覆盖tests/。参见FINAL_COMPARISON.json及两份result。历史6b9c255比较单独保留。
- Both baseline/current candidate ran833 tests with identical37 failure/17 error IDs and zero new IDs, not all green; scope tests/. See FINAL_COMPARISON.json and both result files. Intermediate6b9c255 evidence is retained separately.
- 60文件真实包已stage、bootstrap逐文件核验、包内执行测试、回滚ABSENT通过。首次检查6002a5b在深目录触发路径故障；另一次验证脚本未加-B生成pycache，被UNMANAGED_FILES正确拒绝。按真实服务-I -B方式重新验证通过，旧隔离目录保留。
- The60-file real package passed staging, bootstrap verification, packaged execution tests and rollback to ABSENT. An initial6002a5b deep-root check exposed the path bug; a separate harness without-B generated pycache and was correctly rejected as UNMANAGED_FILES. Verification using the service's-I -B policy passed; old isolated directories are preserved.

安装ZIP / Install ZIP SHA256: `046cfd72d783bf09dac704a5b359b03421933f90d1078c2a8dd297a3f89e33be`
回滚工具ZIP / Rollback tools ZIP SHA256: `8cfec97c4bafd5a200ab2a5f3147edb58d2da66dd104697a95586003080cf76e`
清单 / Manifest SHA256: `11481e186c7556bf406eb41ed1c0589daf560906ff1b23e6c6c7468cb870e219`

剩余交付阻断 / Remaining delivery blockers:
正式服务/8791与原Inventory拥有者尚未接入该离线事件入口；生产backend准入、身份/ACL、Python依赖不可变保护、SCM升级和完整文件回滚仍未闭环。Windows临时stdin可能有磁盘临时文件，生产ACL必须验证。文件句柄pin不证明全部祖先目录/硬链接/TOCTOU与维护租约安全。独审PENDING，未安装、启用、部署服务。回滚工具包依赖现场versions/backups，不是完整现场备份。
Formal service/8791 and original Inventory owner are not yet wired to this offline event consumer. Production backend admission, identity/ACL, immutable Python dependencies, SCM upgrade and complete file rollback remain open. Windows temporary stdin can be disk-backed and requires production ACL verification. File pins do not establish complete ancestor/hardlink/TOCTOU or maintenance-lease safety. Independent review PENDING; no service installation, enabling or deployment. Rollback tools depend on retained site versions/backups and are not a complete site backup.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false

下一动作：接通原Inventory拥有者与宿主事件消费入口，保持派发门禁关闭；补齐身份/ACL/依赖保护及SCM升级和完整文件回滚，固定候选独审后才安装。
Next action: Wire the existing Inventory owner to the service event consumer with closed dispatch gates; finish identity/ACL/dependency protection and SCM upgrade/full-file rollback, then independently review the frozen candidate before installation.

---

# 安装配置集成 / Installer configuration integration

更新时间 / Updated: 2026-11-02T06:58:13.090340+00:00
固定源码 / Fixed source: a5751e8e67ceeac6e9568571ecf7c69c074ec952

已按 Issue2 评论6567493676 修改真实安装器：从独立批准哈希的配置计划自动生成 runtime.json 与 supervisor.json；绑定Python、bootstrap、配置哈希，拒绝过期认证、路径与输入漂移；CreateNew及逐字节回读，执行安装缺计划拒绝。没有执行安装。
The real installer now generates runtime.json and supervisor.json from a separately hash-approved reference plan. It binds Python/bootstrap/config hashes, rejects expired credentials and path/input drift, uses CreateNew and byte readback, and refuses execution without a plan. Installation was not executed.

组合测试37项通过，11.385秒。先前测试因Windows PowerShell环境缺命令失败，改为当前pwsh运行；UTF8读回修复后组合通过。测试只隔离执行配置生成块，未验证真实管理员安装、ACL或服务启动。
37 combined tests passed in11.385s. Initial Windows PowerShell environment lacked the command; current pwsh and UTF8 capture pass. Provisioning tests execute the actual configuration-generation block in isolation, not administrator installation, ACL or service startup.

安装包 / Install zip SHA256: 36616471b9f09707649c34e5335c1c18f19d7d326af88d3ecf29740bc88b3a03
回滚工具包 / Rollback tools SHA256: 9672e93d1b19f4040bfaf5871d44f7131b825a6319a3898c83a7a6665c9d9216
清单 / Manifest SHA256: a205e30534780af9c8ca2169e25ea91656015a9e6d7636408df62188e7677deb
回滚工具不是现场完整备份。独审PENDING，生产安装未执行。发布器目标身份、reparse/hardlink/TOCTOU、升级和完整回滚尚未闭环；本次哈希检查不构成并发替换防护。正式backend与原Inventory准入尚未接通，不把只读8791服务称为自动执行。
Rollback tools are not a complete site backup. Independent review PENDING; no production installation. Publisher target identity, reparse/hardlink/TOCTOU, upgrade and full rollback remain open; hash checking does not establish race protection. Formal backend/original Inventory admission is not integrated; readonly8791 is not automatic execution.

原自动任务rokt-razo已更新，仍每3小时，Prompt限制45分钟和最多两条重线；平台未提供硬超时字段。Prompt SHA256: 0e61d66affd96889ba921a73e60aa23180ade5d37d78f7797b8dd24e34aeaf42
Existing automation rokt-razo was updated, retaining3-hour cadence, a45-minute prompt budget and at most2 heavy workstreams. No platform hard-timeout field was provided.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN

下一动作 / Next action: Integrate bounded execution backend with existing signed SingleSlotAdapter admission and original Inventory lease; close installer upgrade/rollback, dependency ACL and TOCTOU blockers before independent review. No service install/start.

---

2026-10-30 U1增量：079792aa新增路径无关的恢复日志快照状态层，23组合/23独立项通过，7新增项；10文件固定源码隔离导入通过。COMPLETED仅日志阶段，不授予生产终态/锁关闭/重放。仅新状态层独审通过，旧833结论不扩到本pin。WB main仍13572ee9/Issue2仍6513015427。整体开发/发布/部署/生产验收仍false，下一步隔离HTTP状态接入，保留启动前未提交文件。详见../u1_recovery_status_20261030/REPORT.md。

2026-10-30 increment079792aa adds path-free recovery snapshot status:23 combined/23 independently run tests pass, including seven new tests, plus10 pinned source imports. COMPLETED is journal phase only, never terminal/lock/replay authority. Scoped status review passes; old833 regression is not extended. WorkBuddy main13572ee9/Issue2 6513015427 unchanged. Overall development/release/deployment/acceptance remain false. Next: isolated HTTP/status integration, preserving existing uncommitted files. See the new report.

---

2026-10-30 U1固定候选d7d424c：取消终态持久恢复离线闭环、默认禁用宿主工具及真实开发包已实现；239组合/85独立项通过，833基线与候选同37失败17错误ID，新增回归0但非全绿。整体离线独审/运输审核通过。生产宿主8791/Python/backend与31门禁尚未满足，DEVELOPMENT_COMPLETE/RELEASE_READY/PRODUCTION_DEPLOYED/PRODUCTION_ACCEPTED=false。Issue2新候选只读兼容交接6513015427已逐字回读；下一步补接口接入并自动消费WorkBuddy，不重复旧合同。SMTP关闭，无生产DB/安装/权限修改。此为用户指令工程，不计完整无人值守周期。详见 evidence/u1_p0_final_20261030/REPORT.md。

2026-10-30 pinned U1 d7d424c completes offline durable cancellation recovery, disabled-host tooling and a real development package.239 combined/85 independent tests pass;833 baseline/candidate retain identical37 failure/17 error IDs: zero new regression, not all green. Whole offline source/transport review passes. Production8791/Python/backend and31 gates remain unsatisfied, so overall development/release/deployment/acceptance remain false. Candidate-specific read-only Issue2 request6513015427 was independently matched. Next: integrate missing interfaces offline and consume WorkBuddy evidence without duplicate requests. SMTP off; no production DB/install/permission change. User-triggered engineering is not a complete unattended cycle. See the linked report.

---

# U1交付状态 / U1 delivery status

2026-10-28最新交付入口：U1_REFRESH_DELIVERY.md；固定源码3f03417，113项主线及111项独立测试通过，预算回执绑定缺陷已修复。下文保留历史记录。 / Latest delivery: U1_REFRESH_DELIVERY.md; pinned source3f03417 passed113 main and111 independent tests and repairs receipt binding. Historical text below is retained.

本轮完成回滚计划准入代码，固定15b52672ddd03f94ead05d4db932ca6c07601ec0，独立9项通过，组合98项通过（10.298秒）。更新后的12文件源码清单隔离导入另2项通过（1.068秒）。这不是生产安装包：目标路径和指纹仍UNAPPROVED。 / This iteration implements rollback-plan admission at the pinned revision, with9 independent tests and98 combined tests passing in10.298 seconds. The updated12-file source manifest also passed2 isolated-import tests in1.068 seconds. It is not a production installation package: targets and fingerprints remain unapproved.

## 必填状态 / Required status

```text
PHASE=U1
BASELINE_COMMIT=b3a0d3ae26ef99fea5f458ec029301d233a27f7c
DEVELOPMENT_COMPLETE=false
OFFLINE_TESTS_PASSED=98_CURRENT_SCOPED_TESTS
INDEPENDENT_REVIEW=PASS_FOR_OFFLINE_ROLLBACK_PLAN_ADMISSION
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
DURABLE_SLOT_LEDGER_VERIFIED=OFFLINE_ONLY
ATOMIC_CLAIM_AND_RESTART_VERIFIED=OFFLINE_ONLY
NONINTERACTIVE_EGRESS_READY=UNKNOWN
BRIDGE_CROSS_CALL_VERIFIED=NOT_LIVE_ACCEPTED
BRIDGE_CROSS_LOGON_VERIFIED=NOT_LIVE_ACCEPTED
UNATTENDED_CYCLES_VERIFIED=UNKNOWN
ORIGINAL_INVENTORY_PRESERVED=true
DUPLICATE_INVENTORY_CREATED=false
DAILY_BUDGET_LEDGER_READY=OFFLINE_ONLY
FIRST_QUALIFIED_LEDGER_READY=OFFLINE_ONLY
NEW_UNIQUE_ORGANIZATIONS=UNKNOWN
NEW_FIRST_PARTY_EMAILS=UNKNOWN
SAFE_LATEST=UNKNOWN
SAFE_NET_GROWTH=UNKNOWN
CUSTOMER_SMTP_ENABLED=false
EMAILS_SENT_THIS_TASK=0
PRODUCTION_DB_UNAUTHORIZED_WRITES=0
GIT_COMMIT=15b52672ddd03f94ead05d4db932ca6c07601ec0
PUSH_SUCCESS=true_SOURCE_AND_REVIEW_VERIFIED_AT_d141f932f37072055d65a305a751d619383d65ff
BLOCKERS_REQUIRING_USER=ADMIN_AND_PRODUCTION_CHANGE_APPROVAL_AFTER_REVIEWABLE_PACKAGE
NEXT_AUTOMATIC_ACTION=FORMAL_BACKEND_RUNTIME_AND_PUBLISHER_CONTRACT_INTEGRATION
```

## 距离无人登录稳定运行的条件 / Remaining conditions for login-free operation

仍缺正式唯一Inventory执行合同及硬时限/取消/回执接入、真实Windows身份/排空/锁/跨登录观测生产端、获准非交互网络出口、正式runtime依赖指纹及新增文件发布器兼容。具备可审核包后才申请专用低权限身份、最小ACL、禁用任务注册和安全窗口内唯一权威切换；本轮未执行这些变更。 / Still missing: the sole Inventory backend contract and hard deadline/cancellation/receipt integration; actual Windows identity/drain/lock/session collectors; approved noninteractive egress; production runtime fingerprints and new-file publisher compatibility. Only a reviewable package can precede the minimum identity/ACL/disabled-task/window/cutover approval. None were executed.

可交付成果是已审核的持久slot、预算及首次资格账本、离线adapter、桥接证据聚合、快照兼容和回滚准入源码候选；尚不能称可部署生产包。新增合格企业可在合成完整历史、可信身份和冻结baseline条件下独立计量，但没有新鲜正式全历史和真实观测，当前业务增长仍UNKNOWN。 / Deliverables are reviewed source candidates for durable slots, budget/first-qualification ledgers, offline adapter, bridge evidence, snapshot compatibility and rollback admission, not a deployable production package. Independent measurement works with complete synthetic history, trusted identities and frozen baselines; absent fresh formal history and observations, current business growth remains UNKNOWN.

Issue2最新仍6435605069，不重复申请。旧833项比较只覆盖b69214d，同37失败17错误，非全绿；不能扩大到最新候选。回滚门禁签名只证明声明来源，不能证明OS事实；allow_dispatch始终false。 / Issue2 still ends at6435605069; no duplicate requests. The old833-test comparison applies only to b69214d, with identical37 failures/17 errors, not all green. Signatures establish provenance rather than OS truth; allow_dispatch remains false.

报告自检：中英双语，实际测试与限制、未执行项和下一步明确，无客户资料或凭据。 / Self-check: bilingual, explicit actual tests, limits, exclusions and next steps; no customer information or credentials.
