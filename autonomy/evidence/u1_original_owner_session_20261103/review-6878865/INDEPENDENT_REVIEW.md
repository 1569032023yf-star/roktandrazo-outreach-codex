# 原owner会话接线独审 / Independent original-owner session integration review

结论：`OFFLINE_SCOPED_REVIEW_PASSED`。固定源码 `68788653c848659c63f85021075fedee4aca5b13`，基线 `6e95089cee61b06ac6d8fafcceb536b01a66087c`。本轮已报两项P1与一项P2均关闭，审核范围内无新增未解决阻断。`RELEASE_READY=false`、formal backend和生产派发门禁保持false。

Conclusion: scoped offline review passed. The two reported P1 findings and the P2 alias finding are closed; no additional unresolved blocker was found in this scope. This is not formal backend, installation, release or production approval.

## 安全与恢复核查 / Safety and recovery review

原锁的BEGIN IMMEDIATE同时写holder、进程incarnation、随机nonce与数据库身份，并可返回该事务产生的精确binding。实际stage将binding保存在本次调用局部变量，finally显式传expected_owner；释放事务内核验该binding、holder、PID incarnation、维护状态与树状态。缺失binding、旧nonce、死进程、未知树均拒绝。没有在release现场重新采集当前会话冒充旧调用者身份。

The original immediate transaction persists the owner incarnation and returns its exact binding. Actual stage code retains it locally and passes it explicitly to release. The release transaction checks identity, maintenance exclusion and tree state; missing or stale bindings cannot release a replacement owner.

原event intent先于HTTP、预算和claim持久化，将树置unverified；单owner不允许第二event。预算先持久预留，随后claim并将exact common+claim token hash写入原session，才允许backend。跨数据库半提交保守保留slot/预算/原树封锁。operation与两类受信receipt绑定当前owner、event摘要及claim摘要；reconcile先匹配session claim，再复用原slot与预算核验，只有两本账都确认后才将原树置verified_closed。原会话身份未冒用supervisor.lock。

Event intent is durable before transport or claiming. The budget reservation precedes the slot claim; the original session then records its exact claim join before backend entry. Partial writes preserve fences. Operation and authenticated receipts bind the current owner/event/claim, and final tree closure follows both durable ledgers, not normal callback return. The original DB owner is not impersonated by a supervisor lease.

取消journal保护原DB、slot和budget的main与-journal/-wal/-shm保留路径，不要求侧文件预先存在；存在时另核验实际文件别名。observer仅观察受信连接工厂给出的原数据库，验证单一活跃原owner、PID incarnation与数据库身份。HTTP不能注入数据库路径。

Cancellation-journal checks protect main databases and reserved SQLite sidecars, including absent sidecars and existing aliases. The observer uses a trusted connection factory and verifies a unique live original owner and database identity; HTTP cannot choose that database.

## 独立测试与探针 / Independent tests and probes

独立执行119项，0 failure / 0 error；两个runner测试耗时23.104与8.543秒，合计31.647秒（合计测试耗时，非总墙钟）。实际命令、分组、源码文件SHA256及Git blob摘要见JSON。覆盖原owner、原排他、single-slot、预算、当前stage、真实HTTP事件及真实子进程backend协议。没有继承未固定工作树22项的成绩。

119 tests passed independently on the pinned source. Summed runner durations were31.647 seconds, not total wall time. Exact commands and file hashes are in JSON. Earlier working-tree runs are diagnostic only.

额外注入claim join提交前失败、提交成功后回包丢失：两者均0 backend调用，树保留unverified、原锁拒绝释放，再次execute也不调用backend。另20轮原release与event intent竞争未出现双成功；本次调度全部release先赢，未虚称该探针覆盖intent先赢。独立准备事件相关测试覆盖intent已持久后release拒绝。实际os._exit(29)、丢submit/RESERVED回包、结算失败、旧owner release和旧receipt负例均在固定源码测试组合内重新通过。

Additional claim-join failure cuts before and after commit both retained fences with zero backend calls and no execution on retry. Twenty release/event-intent races had no double success; all observed release-first scheduling, so this probe alone does not claim both interleavings. Prepared-event tests separately verify intent-first release denial. Pinned tests also cover real abrupt child exit, lost transport acknowledgements, partial settlement, stale release and old receipt rejection.

## 范围限制 / Limitations

测试中的HTTP和临时SQLite是真实实现，业务backend是隔离替身。正式Provider、完整受信命令与生产运行接线未因此完成；真实Windows SCM/ACL成功和生产验收仍需另证。未修改生产数据库、Inventory、ACL、服务、现场文件或配置；未读取生产凭据。未知owner死亡仍持续封锁，不新增调度器、自动重放或强制释放。

Loopback HTTP and isolated SQLite use real implementations; business execution uses test doubles. Formal Provider integration, complete production command wiring, actual Windows SCM/ACL success and production acceptance remain unproven. No production state or credentials were accessed. Dead unknown owners remain fenced; no scheduler, automatic replay or forced release was added.

## 实际制品补充核验 / Actual artifact verification supplement

同固定6878865的工程包72项payload全部摘要通过；源码映射59项与Git blob逐字节相同、7项host源码仅CRLF/LF差异，另6项明确为生成制品/观察（包括PE及清单），没有把生成文件伪称原Git blob。install.zip 73条文件、rollback-tools.zip 18条文件逐字节匹配磁盘布局及BUILD摘要，内外manifest一致；PE machine=AMD64 0x8664。

All 72 payload hashes passed. Mapping distinguishes 59 exact Git blobs, 7 host-source newline-equivalent files and 6 generated artifacts/observations. The install and rollback archives contain 73 and 18 files respectively, matching their disk trees and BUILD hashes byte-for-byte; the PE is AMD64. This does not establish independent reproducible compilation.

原owner companion 8项payload均逐字节匹配固定Git blob，manifest及ZIP摘要通过；expected_before逐项与3bbb固定Git基线比对，明确不是现场取证。新临时解压、Python -I -B独立导入原owner/维护helper依赖闭包通过；未执行bd_db/bd_orchestrator顶层或main，未读配置、数据库或凭据。companion不是全部原业务运行依赖的自包含安装器；原业务既有依赖仍由原环境提供。

The eight companion payloads match pinned Git blobs exactly. Baseline conditions were checked against 3bbb Git bytes, not site evidence. Fresh isolated helper import passed without executing bd_db/bd_orchestrator top-level code or main, configuration, databases or credentials. This companion is not a self-contained installer for every original business dependency.

已只读确认固定源码test_process_backend包含1e999与-1e999 worker真实返回负例，该模块在此前独立119项组合的13项runner内已执行，非追加未运行的声明。其结果要求UNKNOWN且禁止重放。详细逐文件映射、摘要及范围限制写于INDEPENDENT_PACKAGE_RESULT.json。无自动更新器、不扩大宿主白名单，所有生产与可安装门禁仍false。

Pinned test_process_backend includes positive and negative exponent overflow worker outputs (1e999 and -1e999), already executed in the 13-test runner counted in the independent119. They require UNKNOWN and no replay. Full mapping and hashes are in INDEPENDENT_PACKAGE_RESULT.json. No updater or host allowlist expansion is supplied; installation and production gates remain false.
