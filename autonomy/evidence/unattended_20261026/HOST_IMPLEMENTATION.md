# Phase U1 B/C 宿主与证据实现 / Host and evidence implementation

## 已实现 / Implemented

`autonomy/host_preparation.py`实现可信来源白名单、独立注入HMAC密钥、主体及Inventory绑定、规范JSON签名、未来/过期拒绝、receipt标识及精确slot/epoch/owner字段绑定接口。payload中的布尔值或自行声明trusted不能越过签名。密钥不写文件、不读用户凭据；测试密钥仅合成。签名证明来源与完整性，不证明采集者诚实，生产信任根及OS只读采集器仍需正式部署和审核。

The consumer implements an allowlisted source, externally injected HMAC key, principal/Inventory binding, canonical JSON signatures, future/stale/expired rejection, receipt identifiers and exact slot/epoch/owner binding. Self-asserted booleans cannot bypass signatures. Keys are neither persisted nor read from user credentials; fixture keys are synthetic. Authentication proves origin/integrity, not collector truth. Production trust roots and an OS read-only collector still require approved provisioning and review.

`EvidenceConsumer.verify`返回验签后的深拷贝payload；执行账本只能读取这个返回值，不能验签后继续读取未签名顶层字段。`verify_bound`可比较期望绑定且严格区分bool/int。15门禁仍复用现有readiness；非交互出口合同绑定目标执行身份，要求DNS/TLS/代理健康证据及无需用户会话。7877用户会话模式明确阻塞，不发送网络请求。

`verify` returns a deep copy of authenticated payload; ledger integrations must read that return value rather than unsigned outer fields. `verify_bound` compares exact expected bindings including types. The existing15 gates remain. Noninteractive-egress receipts bind the target identity and require DNS/TLS/proxy checks without an interactive session. User-session7877 is blocked without issuing requests.

`runtime_file_check`只读核验显式绝对路径与批准SHA，不启动Python/浏览器。宿主CLI固定退出78并报告缺少trust provisioning/formal adapter，即使所有签名门禁为true也不会派发。没有可开启采集的运行时开关。

Runtime file checks read approved absolute files and compare hashes without executing them. The host CLI exits78 for missing trust provisioning/formal execution adapter. Even all signed-true gates cannot dispatch; no runtime switch enables collection.

桥接消费层验证签名、来源、时效、唯一receipt与POST health语义，分别输出HKCU配置、跨调用、跨登录、无人登录启动状态。两次样本最多证明观测时跨调用；跨登录/无人登录持续验收保持NOT_VERIFIED，需完整OS事件链和正常计划周期。GET404与status400不作为健康证据。

Bridge consumption validates signature/source/freshness/unique receipts and POST health semantics, separately reporting HKCU configuration, cross-call, cross-logon and no-login boot status. Two samples prove at most observed cross-call health. Real cross-logon/no-login acceptance stays NOT_VERIFIED pending complete OS event history and natural scheduled cycles. GET404/status400 are not interpreted as health evidence.

## 禁用配置及权限合同 / Disabled configuration and permission contract

`autonomy/config/u1_host_disabled.xml`默认Enabled=false、AllowStartOnDemand=false、无trigger、IgnoreNew、LeastPrivilege、专用账户及机器runtime占位值。动作只有上述拒绝执行的CLI，1分钟限制。不是已安装任务，也不宣称Windows已接受XML schema；本轮只做XML结构测试。无trigger刻意避免重新定义6小时相位；真实切换只能消费原权威的next_due，不能固定整点cron或创建第二Inventory。

The candidate is disabled, disallows on-demand start, has no trigger, uses IgnoreNew/LeastPrivilege and unresolved dedicated-account/runtime placeholders. Its sole action is the refusing CLI with a one-minute limit. It is not installed; XML structure tests are not Windows schema acceptance. No trigger avoids redefining the6-hour phase; future cutover must consume authoritative next_due, not create a fixed-hour cron or second Inventory.

最小权限候选：专用非管理员账户；仅批准批处理登录；代码/Python/浏览器为管理员维护只读；工作目录不含用户profile；只授予ledger、SQLite journal、cache、logs、audit所需目录修改权。禁止全目录用户profile授权、部署token、SMTP凭据及修改代码权限。ACL、批处理权、实际SID及文件hash必须由正式只读OS采集器签名，不由运行参数自证。本轮未创建用户、改ACL或读任何真实秘密。

Proposed least privilege: dedicated nonadmin account with approved batch logon; administrator-maintained read-only code/Python/browser; no user-profile working directory; modify rights only on ledger/SQLite-journal/cache/log/audit directories. No broad profile grants, deployment tokens, SMTP credentials or code mutation rights. A formal read-only OS collector must attest ACLs, batch rights, SID and hashes; CLI assertions cannot prove them. No accounts/ACLs/secrets were changed/read.

Password批处理登录需要注册时通过管理员安全交互提供独立凭据，不得写入XML或日志；S4U无网络/加密文件能力，不能默认替代。独立非交互网络出口需供应方许可和目标身份实测；不复制用户代理配置。HMAC验证者掌握对称密钥，故验证进程必须与未信任输入隔离；生产应由已授权密钥保管/签名机制接入，当前无正式adapter、持续拒绝。

Password batch logon requires secure administrator credential entry at registration, never XML/log storage. S4U lacks network/encrypted-file access and is not the default. Noninteractive egress needs approval and target-identity testing; user proxy configuration is not copied. HMAC verifiers possess a symmetric key and must be isolated from untrusted inputs; production requires an authorized signing/key-custody integration. No formal adapter is installed, so execution stays denied.

## 故障、回滚及真实验收 / Failure, rollback and live acceptance

网络/浏览器/SQLite失败不得重放可能已派发的slot；由A账本保存UNKNOWN并保留预算，正式对账后恢复。宿主退出不等于Provider未发生；仅业务账本及原锁可决定后续动作。新权威启用前禁用旧派发、排空并对账、核实原锁和epoch；回滚先禁用新派发并排空，对账UNKNOWN，再恢复旧权威；不得同时启用、删除ledger或回退业务数据库。

Network/browser/SQLite failures cannot replay potentially dispatched slots. A's ledger must retain UNKNOWN and reservations pending formal reconciliation. Host exit does not prove absence of Provider effects. Cutover requires stopping old dispatch, draining/reconciling and checking the original lock/epoch. Rollback disables and drains new dispatch, reconciles unknown outcomes, then restores the old authority; never enable both or delete ledgers/business history.

真实验收步骤：维护窗口内由授权运维完成禁用态注册及身份/ACL验证；批准非交互出口后使用目标账户只读探测；原权威排空后才切换；观察两个连续原语义正常周期，关联OS boot/logon与调度审计，证明无交互登录依赖。8791另以正常登录后两个独立POST health、会话及进程启动标识采样；跨登录/重启需明确窗口，不在Agent内绕Job限制启动。

Live acceptance requires authorized disabled registration and identity/ACL checks, approved target-account egress probes, drained single-authority cutover, then two normal cycles correlated with OS boot/logon and scheduler audit proving no interactive dependency. Bridge acceptance separately uses two independent POST health observations after normal login, with session/process-start identity. Cross-logon/reboot requires an explicit window; no Agent job-limit workaround.

## 测试与状态 / Tests and status

命令 / Command: `python -B -m unittest test_host_preparation test_unattended_policy test_bridge_acceptance -q` — 18 PASS。首次17项运行发现测试sign helper共享payload导致测试间污染，改为deepcopy后通过；随后新增绑定/过期用例18项通过。未运行浏览器或全量suite，内存不足1GB时仅轻量定向测试。没有生产操作、安装、采集或SMTP。

Initial17-test execution exposed shared fixture payload mutation; deepcopy fixed the fixture. Added binding/expiry coverage brings18 passing tests. No browser/full suite was run, respecting low-memory limits. No production action, installation, collection or SMTP occurred.

B/C离线候选已实现，独审PENDING；生产adapter、OS可信采集器部署、trust根、目标身份、ACL、非交互出口、原权威兼容切换与维护窗口仍缺。RELEASE_READY=false，PRODUCTION_DEPLOYED=false，PRODUCTION_ACCEPTED=false；四项真实桥接状态没有新增生产观测。报告中英双语、无秘密、自检完成；下一步独立审核及与A账本集成。

B/C offline candidate is implemented with independent review PENDING. Missing production adapter, deployed OS collector/trust root, target identity/ACLs, noninteractive egress, compatible authority cutover and window keep release/deployment/acceptance false. No new live bridge observations exist. Bilingual/sensitive-data self-check completed; next independent review and A-ledger integration.

官方依据 / Official references:
- https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype
- https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-multipleinstancespolicy-settingstype-element
- https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-settingstype-complextype
