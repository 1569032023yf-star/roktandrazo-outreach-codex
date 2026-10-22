# C 可靠性修复开发交付 / Reliability repair developer handoff

结果 / Result: ENGINEERING_TESTED_AWAITING_INDEPENDENT_REVIEW_AND_REAL_HEARTBEAT_ACCEPTANCE.

保留既有未提交的有界输出与Windows Job候选，在其基础上补修R2/R3/R4。未修改生产代码、客户库、SMTP或自动调度器。
Preserved the existing uncommitted bounded-output and Windows Job candidate and repaired R2/R3/R4 on top. No production code, customer database, SMTP or scheduler was modified.

## 修复 / Repairs

- R2：supervisor.exclusive现委派同一schema-v2实例锁协议，包含PID创建身份、不可变token、树状态及创建时间；创建、状态变更、释放和显式恢复共用exclusive recovery guard。legacy锁、仍存活进程、未知进程身份及未验证进程树均拒绝恢复。不依赖锁年龄自动删除。
  R2: supervisor.exclusive delegates to the same schema-v2 process-instance lock protocol with PID creation identity, immutable token, tree state and creation time. Creation, mutation, release and explicit recovery share an exclusive recovery guard. Legacy locks, live instances, unknown identities and unverified process trees remain blocked. No age-based deletion occurs.
- R3：run_agent保留超时及输出限额等固定错误分类、cleanup_verified及脱敏cleanup_errors；失败均为UNKNOWN并沿既有队列隔离，不再丢弃超时清理证据。子进程执行前将树状态记为unverified，只有清理核验通过才记verified_closed；未验证清理的锁保持阻塞。
  R3: run_agent retains fixed timeout/output-limit classifications, cleanup_verified and sanitized cleanup_errors. Failures remain UNKNOWN and use existing queue quarantine, preserving timeout cleanup evidence. Tree state is persisted as unverified before launch and verified_closed only after verified cleanup; locks with unverified cleanup remain blocked.
- R4：输出reader的close异常纳入独立清理错误列表，reader读失败仍保留主异常；无reader启动路径的stream关闭也被捕获，不覆盖既有主错误。
  R4: Reader close errors are retained as cleanup failures without replacing primary read errors. Stream-close failures before readers start are also captured without replacing the primary failure.

## 验证 / Validation

本地46项process/lock/supervisor回归通过，包含真实Windows父子进程PID终止核验、真实子进程崩溃后实例锁恢复、仍存活/legacy/未知树拒绝恢复、guard互斥、清理异常保留主错误、输出限额、reader-close故障注入、持久化timeout metadata及UNKNOWN无重跑。详见tests.json和tests.log的时间、文件指纹及命令。
All 46 local process/lock/supervisor tests passed, including real Windows parent/child PID termination checks, real subprocess-crash lock recovery, live/legacy/unknown-tree refusal, guard exclusion, primary-error preservation, output bounds, reader-close fault injection, durable timeout metadata and no UNKNOWN rerun. See tests.json and tests.log for timestamps, source fingerprints and command.

未执行 / Not executed: 独立Reviewer尚未审核；没有新增真实系统心跳周期，没有生产发布或自然业务验收。测试不能替代真实无人值守多周期证据。AUTONOMOUS_OPERATIONS_ACTIVE仍不得升级true。
Independent review is pending. No new actual system-heartbeat cycles, production release or natural business acceptance occurred. Tests do not substitute for genuine unattended multi-cycle evidence; AUTONOMOUS_OPERATIONS_ACTIVE must not be promoted to true.

风险 / Risks: 崩溃发生在tree_state=unverified期间时，本协议有意保留锁并要求外部只读清理证据，不根据PID死亡就释放可能仍有后代的锁。POSIX路径本机未执行；本机证据为Windows。Windows隐藏Job对象/句柄失败为本地故障注入，不是生产故障。
A crash while tree_state=unverified deliberately retains the lock and requires external read-only cleanup evidence; parent death alone does not justify releasing a lock whose descendants may survive. POSIX execution was not tested on this host; evidence is Windows-specific. Windows API/handle failure tests are local fault injection, not production incidents.

下一步 / Next: 独立审查最终diff、失败路径与测试计数；审核通过后由总控提交，使用既有心跳对真实队列领取、故障隔离、续接及副作用对账进行多周期验收，不创建第二个总控。
Independently review the final diff, failure paths and test counts; after approval, the parent commits and uses the existing heartbeat to verify actual queue leasing, failure quarantine, continuation and side-effect reconciliation across genuine cycles, without a second supervisor.

自查 / Self-check: 双语、执行与未执行、数量、风险和下一步均已列出；没有读取或输出凭据与客户内容，没有把开发验证写成生产/无人值守验收。
Bilingual results, unexecuted work, counts, risks and next steps are included. No credentials or customer content were accessed or output. Development tests are not presented as production/unattended acceptance.


独立审核补修 / Independent-review repairs: 保留lock state写入失败前的timeout主错误与cleanup证据；reader-close步骤及根因分类保留到持久化队列。真实Windows复测还发现已退出进程对象可能因其他句柄保留，现通过WaitForSingleObject确认存活后再读取创建身份，新增保留已退出进程句柄的确定性测试。 / Preserve timeout primary and cleanup evidence when lock-state persistence fails; retain reader-close step and cause classifications in durable queue. Real Windows reruns also found an exited process object may remain due to retained handles; WaitForSingleObject now verifies liveness before creation identity, with a deterministic retained-handle regression.
