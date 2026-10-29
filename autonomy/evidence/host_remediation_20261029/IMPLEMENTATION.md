# 主机持久化修复增量 / Host persistence remediation increment

依据 / Scope: Issue #2 comment6492756398. Fixed source: `922a6965a80c6eb3c06ba15896821f208e013a19`; baseline `e3ac89cbe182ba3e2494f23a1f3e671a974b7d68`.

中文：本轮交付离线拒绝式主机合同校验器、单一禁用服务候选声明、只读PowerShell观察脚本和固定Git字节清单。并未交付可安装Windows服务或修复生产8791；完整主机修复尚未完成。没有安装、提权、启动、生产网络探测、Inventory运行、生产数据库访问或SMTP操作。缺少CURRENT_STATUS.md和FILE_MANIFEST.md已记录，不开展live send。

English: This increment delivers an offline fail-closed host-contract verifier, one disabled service declaration, a read-only PowerShell observation script and a fixed Git-byte manifest. It does not deliver an installable Windows service or repair production8791; overall host remediation remains incomplete. No installation, elevation, service start, production network probe, Inventory run, production database access or SMTP operation occurred. Missing CURRENT_STATUS.md and FILE_MANIFEST.md were recorded; no live sending is attempted.

## 候选与权限 / Candidate and permissions

中文：唯一候选RoktU1Bridge使用专属虚拟服务账户NT SERVICE\RoktU1Bridge；候选目录C:\Program Files\RoktU1Bridge\v1和状态目录C:\ProgramData\RoktU1Bridge均未批准。SCM注册需正式获授权安装，绝不使用Job Object逃逸或旧BDExecutionHost。代码只读执行，secret仅服务读取，状态仅服务修改；必须逐项核实继承ACL、有效SeServiceLogonRight与客户DB不可访问，不能靠ACL模板推定通过。实际服务包装器、Python版本/哈希、签名发布器、受保护token及正式目标合同仍PENDING；当前JSON为不可安装声明，不是安装完成证据。只读脚本仅检查新候选注册、路径、哈希和原始SDDL，不安装、不启动、不签名，也不判定ACL安全。

English: The sole proposed RoktU1Bridge uses the dedicated virtual service account NT SERVICE\RoktU1Bridge. Proposed code and state paths remain unapproved. SCM registration requires an authorized OS installation, never Job Object escape or reuse of BDExecutionHost. Code is read/execute only, secrets service-readable and state service-writable. Inherited ACLs, effective SeServiceLogonRight and absence of customer-DB access require actual verification. Wrapper, Python version/hash, signed publisher, protected token and approved target contract remain PENDING. The JSON is a non-installable declaration. The observation script only inspects registration, paths, hashes and raw SDDL; it neither mutates nor signs nor accepts ACL safety.

## 后端和恢复 / Backend and recovery

中文：保留唯一Inventory1784775229336，不建触发器。合同绑定经外部批准的source/package/runtime/wrapper/publisher/config指纹、principal、lock、backend协议和proxy身份。现有run/firing、operation、claim必须经原适配器与持久ledger逐项绑定；本模块不替代原适配器、不发起命令。仅允许health、status、reconcile_existing_operation；无任意shell/文件或DB入口。旧协议一律拒绝。崩溃、重启、回执丢失保持UNKNOWN和预算、slot、取消journal预留，不重放、不退款；回滚仅停用新注册/候选代码，不恢复陈旧状态。正式publisher兼容和两次原计划自然运行仍为独立门禁。

English: Preserve sole Inventory1784775229336 without triggers. Bind separately approved source/package/runtime/wrapper/publisher/config fingerprints, principal, lock, backend protocol and proxy identity. Existing run/firing, operation and claim bindings remain the responsibility of the original adapter and durable ledgers. This verifier neither replaces that adapter nor issues operations. Only health/status/reconcile_existing_operation are proposed, with no arbitrary shell/file or DB entry point. Reject legacy protocols. Crash, reboot and lost receipts preserve UNKNOWN and all budget/slot/cancellation reservations without replay or refund. Rollback disables only the new registration/candidate code and preserves current state. Publisher compatibility and two original natural cycles are separate gates.

## 网络与证据 / Network and evidence

中文：7877交互代理及陈旧3213都不能成为无人登录验收。候选网络机制为独立获批headless服务代理，不预定端口、不修改.env/global proxy；精确服务身份在注销后访问批准Provider/MX路径及DNS/代理失败拒绝仍待真实验证。31项签名证据门禁缺一不可，严格True，UNKNOWN/PENDING/数字1均拒绝。签名只证明来源，不证明OS事实。全真合成测试仍返回allow_install/start/dispatch/cancel=false。

English: Interactive7877 and stale3213 cannot establish unattended egress. The proposed mechanism is a separately approved headless proxy service, without inventing a port or modifying .env/global proxy. Actual logged-off approved Provider/MX reachability and DNS/proxy fail-closed behavior under the exact service identity remain unverified. All31 signed evidence gates require strict True; UNKNOWN/PENDING/numeric1 fail closed. Signatures establish provenance, not OS truth. Even a fully true synthetic fixture grants no installation/start/dispatch/cancellation authority.

## 验证与审核 / Validation and review

中文：7项新增测试及主机组合40项通过；U1预算/取消/进程故障+主机组合124项通过（22.455秒）。固定清单7份Git字节SHA256/blob已校验，隔离-I子进程导入通过。PowerShell仅语法解析通过，未在生产执行。故障测试覆盖证据拒绝，不是kill-host/logout/reboot的实际操作验收。本轮固定基线/候选均833项、37失败17错误，失败和错误ID集合完全一致，新增回归0，并非全绿；见REGRESSION_COMPARISON.json。独立审核PENDING；本作者自检不冒充独审。取消费用9b28eb9/tests2e7900b的独审仍待完成。

English: Seven new tests and40 host tests passed; the combined U1 budget/cancellation/process-fault and host suite passed124 tests in22.455s. Seven pinned Git-byte SHA256/blob entries verified and an isolated -I import passed. PowerShell syntax parsed successfully without production execution. Failure tests cover evidence rejection, not actual host-kill/logoff/reboot acceptance. Fresh pinned baseline/candidate runs each completed833 tests with identical37 failure and17 error IDs: zero new regressions, not all green. See REGRESSION_COMPARISON.json. Independent review is PENDING; author inspection is not independent review. Cancellation-cost runtime9b28eb9/tests2e7900b review also remains pending.

## 未完成及下一步 / Outstanding work and next actions

中文：通过同一Issue2消费Windows operator按原范围发布的脱敏固定时间合同及只读证据；不重复索取backend合同或旧消费回执。绑定已批准runtime/wrapper/publisher及有效身份/ACL后，实施真正disabled-only安装产物，完成独审与发布兼容。完整获审包之前不发出安装授权请求；届时一次请求明确身份、路径、提权、维护窗口、安装/启动/切换及保留ledger的回滚范围。当前生产派发和取消派发均false，现有Inventory不变。

English: Consume sanitized fixed-time operator contracts and observations through the existing Issue2 scope without duplicating backend requests or the prior consumption receipt. Bind approved runtime/wrapper/publisher and effective identity/ACL, implement the actual disabled-only installation artifact, then complete independent review and publisher compatibility. Defer the single specific authorization request until the complete reviewed package exists; it must identify identity, paths, elevation, window, install/start/switch and state-preserving rollback. Production dispatch and cancellation remain false; existing Inventory is unchanged.

| 验收 / Acceptance | 状态 / Status |
|---|---|
| BRIDGE_CROSS_CALL_PERSISTENCE | NOT_PASSED_LAST_EVIDENCE |
| BRIDGE_LOGOFF_REBOOT_PERSISTENCE | PENDING |
| NONINTERACTIVE_PROXY_EGRESS | UNKNOWN |
| SERVICE_IDENTITY_ACL | PENDING |
| GLOBAL_INVENTORY_UNIQUENESS | PENDING_LIVE_PROOF; original preserved |
| NATURAL_RUN_2_CYCLES | PENDING_POST_REMEDIATION |
| LEDGER_RECOVERY | OFFLINE_TESTED; host/reboot PENDING |
| SMTP_DISABLED | REQUIRED; historical observed OFF; no fresh probe |
| RELEASE_READY | false |
| PRODUCTION_DEPLOYED | false |
| PRODUCTION_ACCEPTED | false |

SAFE/增长本轮无新采样，当前UNKNOWN。既有WorkBuddy固定5a2906消费记录保持原样。 / No fresh SAFE/growth sampling occurred; current values are UNKNOWN. Preserve the prior fixed5a2906 consumption record.
