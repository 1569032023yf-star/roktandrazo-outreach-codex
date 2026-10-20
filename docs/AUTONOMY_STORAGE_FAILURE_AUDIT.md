# 存储故障恢复独立审核 / Independent storage recovery audit

记录时间 / Recorded: 2026-10-20T06:56:18.171775+00:00

真实触发 / Trusted trigger: 2026-10-20T06:51:15.470Z
周期 / Cycle: 925bf28f-489f-4af9-817f-e596bbd041cf
调度 / Scheduler: codex_heartbeat
执行时间 / Execution: 2026-10-20T06:51:33.107434+00:00 to 2026-10-20T06:54:27.190009+00:00
输出SHA256 / Output SHA256: c511d3e60637c2470c959acc2b889a0a900001a535a7fa79aef533e39189b65b

已完成只读静态审核，核查两份脱敏失败周期记录及现有测试源码。b144cb9a记录为完成持久化时ENOSPC、代理结果UNKNOWN；bfc6ed84为手动重试约600秒后AGENT_TIMEOUT，不能认定原因相同。发现5项可靠性问题，以下给出最小修复及测试建议。未运行测试、联网、修改文件、创建调度器或清理用户文件；未读取凭据、原始候选或生产数据库。实际故障调用栈、超时根因及历史进程清理结果未验证。

Completed a read-only static review of source, existing tests and two sanitized failure receipts. Cycle b144cb9a records ENOSPC during completion persistence with UNKNOWN agent outcome; manual retry bfc6ed84 records AGENT_TIMEOUT after approximately 600 seconds. A common cause is not established. Five reliability findings follow with minimal fixes and test proposals. No tests, networking, file changes, scheduler creation, user-file cleanup or access to credentials, raw candidates or production databases occurred. Historical stack traces, timeout cause and actual process cleanup remain unverified.

## HIGH — autonomy/supervisor.py:212-250

中断的running任务在attempts<3时直接重新排队，并可在同一周期再次执行；超时、RUNNER_EXCEPTION和不完整输出也采用通用重试。完成写入ENOSPC可能发生在开发操作已经完成之后，因此结果未知不等于未执行。needs_reassessment只是标记，不阻止eligible选择。最小修复：把中断、超时及执行后持久化失败归为UNKNOWN并阻止自动重执行；仅经只读核对成果或明确幂等协议后恢复。测试：让有副作用的假runner计数一次，再注入完成写入ENOSPC、超时或不完整输出，恢复后断言调用次数仍为1。

Interrupted running tasks with attempts below three are requeued and may execute again in the same cycle. Timeouts, runner exceptions and incomplete output also receive generic retries. Completion-persistence ENOSPC can follow completed development side effects, so unknown does not mean unexecuted. needs_reassessment does not gate eligibility. Minimal fix: quarantine interrupted, timed-out and post-execution persistence failures as UNKNOWN; resume only after read-only artifact reconciliation or an explicit idempotency protocol. Test with a side-effect counter and injected completion ENOSPC, timeout or incomplete output; recovery must leave the count at one.

## HIGH — autonomy/supervisor.py:39-50,86-90,232-251

单文件写入已使用同目录临时文件、flush、fsync和replace，但最终queue提交失败不在异常处理范围内，旧queue会保留running租约，内存outcome丢失。queue提交成功而receipt失败则可由reconcile恢复，这两种情况必须区分。reconcile还会每轮重写全部历史终态记录。最小修复：为执行后提交失败设置明确故障状态并停止派发；只重建缺失或不一致的receipt，保留queue为权威记录；临时文件清理错误不得覆盖原始写入错误。测试分别注入dump、flush、fsync、replace和receipt写入失败，验证旧JSON完整、未知任务不重跑、receipt可补建。原子替换不能解决外部操作与本地记录之间的事务缺口，也未证明断电持久性。

Individual writes use same-directory temporary files, flush, fsync and replace, but final queue-commit failures escape handling, leaving a running lease and losing the in-memory outcome. A successful queue commit followed by receipt failure is recoverable through reconcile and must be distinguished. Reconcile also rewrites all terminal history each cycle. Minimal fix: explicitly classify post-execution commit failure and stop dispatch; rebuild only missing or inconsistent receipts while retaining queue authority; preserve the primary write exception if temporary-file cleanup fails. Inject failures at dump, flush, fsync, replace and receipt creation. Verify intact old JSON, no unknown-task rerun and receipt reconstruction. Atomic replacement does not provide a transaction with external effects or prove power-loss durability.

## MEDIUM — autonomy/supervisor.py:205-234; autonomy/process_job.py:107

启动前没有空间检查。runtime状态、开发工作树与系统TEMP可能位于不同卷；租约成功落盘不能证明输出或完成提交仍有足够空间。最小修复：在启动代理前检查这些实际路径所在卷，设置可配置最低余量并预留状态提交预算；检查失败时不调用runner，不通过删除用户文件腾空间。测试使用模拟disk_usage覆盖不同卷、低空间和检查异常，断言代理未启动。预检查存在竞争窗口，只能降低风险，不能替代运行期限额和写入失败处理。

There is no pre-launch free-space check. Runtime state, the development tree and system TEMP may occupy different volumes; persisting a lease does not establish capacity for output or final commit. Minimal fix: check the actual destination volumes before launching, with configurable headroom and a state-commit reserve; fail without invoking the runner or deleting user files. Mock disk_usage for separate volumes, low capacity and check errors, asserting no launch. Preflight checks have a race window and cannot replace runtime limits or write-failure handling.

## HIGH — autonomy/process_job.py:14-21,107-145; autonomy/supervisor.py:178-202

Windows stdout/stderr临时文件无字节上限，等待期间不检查大小，结束后read()全量读入；POSIX communicate()同样无限缓冲。随后JSON事件解析还会放大内存占用。600秒时间限制不构成空间限制。最小修复：持续排空输出并限制累计字节和单事件大小，超过阈值终止进程树，返回OUTPUT_LIMIT且副作用结果UNKNOWN；仅保留有界摘要与必要完成事件。测试覆盖持续stdout、stderr、超大单行及双流同时输出，验证限额、清理和未知结果不重跑。不能据此认定本次ENOSPC由临时输出导致。

Windows stdout/stderr temporary files have no byte cap or size monitoring during the wait and are read in full afterward. POSIX communicate also buffers without a bound; JSON event parsing adds memory amplification. A 600-second timeout is not a storage limit. Minimal fix: continuously drain output with cumulative-byte and per-event limits; terminate the process tree on overflow, return OUTPUT_LIMIT and classify side effects as UNKNOWN; retain only bounded summaries and required completion events. Test sustained stdout, stderr, oversized lines and concurrent streams for limits, cleanup and no automatic rerun. This does not establish temporary output as the cause of the observed ENOSPC.

## MEDIUM — autonomy/supervisor.py:53-64; autonomy/process_job.py:19-27,119-155

Windows正常及超时路径已有Job Object整树终止和ActiveProcesses归零检查，属于有效保护；但异常finally中的TerminateProcess、等待和CloseHandle返回值未核验，不能把所有异常路径称为已验证清理。POSIX仅对TimeoutExpired清理进程组，其他异常缺少统一finally及有界清理确认。supervisor遗留锁会拒绝启动，这是安全行为，但锁恢复缺少代码化的进程身份及关联进程树核查协议。最小修复：统一有界清理，保留主异常并单独报告CLEANUP_UNVERIFIED；仅确认原进程实例及关联工作进程均结束后允许显式恢复锁，不按锁龄或PID单独判断。测试覆盖分配Job失败、等待/查询失败、父进程退出但后代存活及遗留锁；现有测试仅验证常规超时后代未写标记，不能证明历史超时根因或全部异常清理。

Windows normal and timeout paths already terminate the Job Object and check ActiveProcesses reaches zero, providing meaningful protection. Exceptional finally paths do not validate TerminateProcess, wait or CloseHandle results, so cleanup is not verified for every failure. POSIX lacks unified finally cleanup and bounded confirmation for exceptions other than TimeoutExpired. Orphan supervisor locks correctly block startup, but recovery lacks a coded protocol for checking process identity and associated workers. Minimal fix: unify bounded cleanup, preserve the primary error and separately report CLEANUP_UNVERIFIED; permit explicit lock recovery only after confirming the original process instance and associated workers have ended, never from lock age or PID alone. Test Job assignment failure, wait/query errors, surviving descendants and orphan locks. Existing timeout-marker coverage does not prove the historical timeout cause or all exceptional cleanup paths.

## 修复次序与边界 / Repair order and limits

第一项开发只处理未知结果隔离、完成提交失败分类及receipt恢复；后续独立审核通过后再处理空间预检、输出限额和异常进程清理。当前5项发现尚未修复。审核完成不是恢复能力验收通过。

The first development task addresses unknown-outcome quarantine, completion-commit failure classification and receipt recovery. After independent review, address space preflight, output caps and exceptional process cleanup. All five findings remain open. Audit completion is not acceptance of recovery reliability.

04:53:38.608Z触发仅有预检、没有任务完成回执，不计成功；06:51:15.470Z触发与上述独立完成回执匹配。历史三轮成功加本轮为四轮，手动续接不计；历史两连续周期条件已证明，最新两触发不构成连续成功。整体AUTONOMOUS_OPERATIONS_ACTIVE=false。

The 04:53:38.608Z trigger had prechecks only and no completion receipt, so it is not successful. The 06:51:15.470Z trigger matches the independent completion above. Three historical successful cycles plus this one equal four; manual work is excluded. A historical consecutive pair was verified, but the latest two triggers are not consecutive successes. Overall AUTONOMOUS_OPERATIONS_ACTIVE=false.

未执行测试、修复、生产部署、真实采集或发信；历史/业务指标UNKNOWN，旧SAFE56不计新增。生产通道最近检查仍06:49/06:50+08，未在本轮复查。报告已检查双语、证据范围、风险、下一步及敏感信息。

No tests, repairs, production deployment, live discovery or email sending were performed by the auditor. History and business metrics remain UNKNOWN; historical SAFE56 is not new growth. Channel checks remain timestamped 06:49/06:50+08, not rechecked this cycle. Report checked for bilingual content, evidence scope, risks, next steps and sensitive information.

后续任务登记回归14项通过（包括三类开发任务进入独立审核的子测试），角色错配被拒绝；此结果不证明5项问题已修复。

The 14 task-registration regressions passed, including independent-review queuing for three developer task types; role mismatches are rejected. This does not establish fixes for the five findings.
