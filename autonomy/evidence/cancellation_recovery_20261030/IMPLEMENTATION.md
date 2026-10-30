# U1取消终态持久恢复 / U1 durable cancellation-terminal recovery

中文：实现独立版本化`rokt.offline-cancel-recovery.v1`编排。原schema1取消journal保持原样，只追加独立SQLite恢复日志（PREPARED/COMPLETED及旧锁事实handoffs）。签名恢复权威绑定当前进程实例、精确旧锁字节SHA、目标路径身份、原journal binding与四份固定签名证据的payload哈希。四证据为取消终态、原slot终态、原执行预算及独立取消费用回执；原claim、原预算与费用binding均与当前持久账本核对。

English: Implements the separate versioned `rokt.offline-cancel-recovery.v1` composition. The original schema1 cancellation journal remains immutable. A separate SQLite log stores PREPARED/COMPLETED and audited old lock facts. Signed recovery authority binds the current process instance, exact previous lock-byte SHA, target identity, persisted journal binding and payload hashes of four fixed signed proofs: cancellation terminal, original slot terminal, original execution budget and independent cancellation cost. Current durable claim/budget/cost bindings are checked before progress.

中文：顺序为保留恢复门禁→PREPARED durable commit→slot终态→独立费用结算→原执行结算→COMPLETED durable commit→最后verified_closed。任何中间故障保持UNKNOWN与unverified，同固定证据可重开SQLite幂等继续；换终态/费用回执拒绝，不自动重派。费用overrun不允许关闭栅栏。普通adapter execute/reconcile以及reserve_then_claim在recovery_only/recovery_required锁中硬拒绝，不能绕开恢复日志提前释放。

English: Ordering is recovery gate, durable PREPARED, slot terminal, independent cost settlement, original-budget settlement, durable COMPLETED, and finally verified_closed. Intermediate failures retain UNKNOWN/unverified; reopening SQLite resumes idempotently with the same fixed proofs. Changed proofs are rejected and no execution is replayed. Overrun costs cannot close the fence. Normal adapter execute/reconcile and reserve_then_claim reject recovery-only leases, preventing ordinary reconciliation from bypassing the durable recovery log.

中文：原进程真实退出后，专用恢复路径仅在既有guard内验证原PID创建身份已死、原锁字节未变和签名恢复权威后接管，保留原token与旧锁事实，标记recovery_only。未知存活状态失败关闭。guard改为版本化持久文件上的Windows内核字节锁/Unix flock，进程退出释放OS锁；完整marker经临时文件fsync和os.link原子发布，不暴露半初始化空文件。旧空O_EXCL guard拒绝且不删除。新marker使旧执行器O_EXCL失败；生产迁移/回滚不得恢复旧执行器继续运行，必须停用并保留全部账本及guard。

English: After actual owner-process exit, explicit recovery takes over only under the existing guard after checking the original PID creation identity is no longer alive, exact old lock bytes, and signed recovery authority. It preserves the token and audit facts and marks the lease recovery-only. Unknown liveness fails closed. The guard uses Windows kernel byte locking or Unix flock on a stable versioned file; process exit releases the OS lock. A complete fsynced temporary marker is atomically published with os.link. Legacy empty O_EXCL guards are rejected without deletion. The new marker blocks legacy O_EXCL executors. Production migration/rollback must disable execution and preserve all ledgers and guard, rather than run an old executor.

## 实测 / Executed validation

- `python -B -m unittest test_cancellation_recovery -q`: final7 tests passed,6.941 seconds, including fresh signed authority over substituted lock identities being rejected.
- 较早组合 / Earlier combination: 50 passed,17.835 seconds; superseded by the final combined run below.
- `PYTHONUTF8=1 python -B -m unittest autonomy.test_lock_recovery test_cancellation_recovery test_single_slot_adapter test_cancellation_cost test_cancellation_settlement -q`: final65 passed,16.314 seconds, including 8 recovery tests, existing lock tests and new overrun reconciliation coverage.
- 中文：真实子进程先建立UNKNOWN claim后os._exit；第二进程在接管guard内PREPARED commit后os._exit，或在费用settled后os._exit；第三执行上下文无backend实例，显式签名恢复到COMPLETED。验证无backend、原journal字节不变、旧锁审计、账本状态及recovery-only派发拒绝。四进程并发首次初始化guard得到4次互斥递增和完整marker。 / English: Real subprocesses exit after creating UNKNOWN, then during guarded PREPARED commit or after fee settlement. A third execution context with no backend instance performs explicit signed recovery to COMPLETED. Assertions cover immutable journal bytes, audited locks, ledger states and recovery-only dispatch rejection. Four concurrent initializers produce four serialized increments and the complete guard marker.

## 未执行与风险 / Non-actions and risks

中文：独审反馈补强：普通reconcile在任何slot/预算写入前先持久标记unverified；只有settle结果为SETTLED/DUPLICATE且回读实际reservation.state为settled才关闭。超额及重复超额均保留fence与UNKNOWN。恢复入口在PREPARED之前验证target及当前runtime/slot/budget路径ID与初始化绑定一致，并核对runtime设备/inode；替换账本副本路径的负例证明锁、账本及恢复日志不发生写入。最终组合65项通过；此前试验的测试预期错误已修正，未隐藏产品失败。

English: Review feedback hardened ordinary reconcile to persist unverified before slot/budget mutation and close only for SETTLED/DUPLICATE plus a reread persisted reservation.state of settled. Overrun and duplicate overrun retain the fence and UNKNOWN. Before PREPARED, recovery validates target/current runtime/slot/budget path IDs and runtime device/inode against initialization. Ledger-copy path substitution tests reject without changing lock, ledgers or recovery log. The final 65-test combination passed; earlier test expectation mistakes were corrected without masking product failures.

中文：补强直接历史绑定：当前锁token哈希必须与journal原lock_token_hash相同；首次非recovery_only锁的process_identity哈希必须与历史journal相同。即使新恢复签名覆盖了替换锁字节也不能替换原锁身份。恢复锁必须同时具备recovery_only和recovery_required。OS明确锁竞争保持既有FileExistsError合同，其它I/O异常不冒充竞争。

English: Direct historical bindings additionally require the current token hash to equal the journal lock_token_hash and the initial non-recovery-only process identity hash to equal the persisted historical identity. A fresh signature over substituted bytes cannot replace original ownership. Recovery leases require both recovery_only and recovery_required. Explicit OS contention preserves the existing FileExistsError contract; unrelated I/O errors are not relabelled as contention.

`PYTHONUTF8=1 python -B -m unittest autonomy.test_lock_recovery test_cancellation_recovery -q`: final19 passed,7.113 seconds. 初次默认GBK遇到已有queue读编码错误，统一UTF-8后通过，未修改测试掩盖错误。 / The initial default-GBK run hit the existing queue-read encoding error; the consistent UTF-8 run passed without changing tests to hide it.

中文：未安装Windows服务、访问生产数据库、采集、发信、变更ACL/注册表/账户/配额，也未授予生产取消或派发。没有断电/磁盘固件保证；原锁写入期间若宿主崩溃造成畸形文件仍失败关闭，需人工正式证据处理。原签名回执必须在受信有效期内，超期不重签替换旧固定证据自动恢复。路径与本地文件系统为可信隔离开发前提；正式目录ACL/签名根/发布器及guard迁移尚待独审和生产兼容验收。最终固定SHA、整体回归及独立审核由主线完成。

English: No Windows service installation, production database access, collection, email, ACL/registry/account/quota changes or production dispatch/cancellation authority. Power-loss and storage-firmware durability are unproven. A malformed lock from interruption during lock-file writing fails closed and requires formal evidence handling. Signed proofs must remain valid; expiry does not permit replacing fixed evidence automatically. Trusted local paths/filesystem are an isolated-development prerequisite. Production ACLs, trust roots, publisher and guard migration await independent review and compatibility acceptance. Parent pins the final SHA and performs combined regression and independent review.

中文：报告自检完成：中英双语、数量/结果/风险/未执行/下一步齐全；无凭据、token、客户资料或完整请求URL。SCOPED_IMPLEMENTED=true，REVIEW_PASSED=PENDING，PRODUCTION_DEPLOYED=false，PRODUCTION_ACCEPTED=false。

English: Report self-check complete: bilingual results/counts/risks/non-actions/next steps, with no credentials, tokens, customer data or full request URLs. SCOPED_IMPLEMENTED=true; REVIEW_PASSED=PENDING; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
