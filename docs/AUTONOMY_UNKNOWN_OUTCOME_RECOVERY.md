# 未知结果隔离与恢复 / Unknown-outcome quarantine and recovery

日期 / Date: 2026-10-20

## 本轮补修与当前验证状态 / Current follow-up and verification status

中文：本节为本轮状态，优先于下文历史测试记录。本轮按独立审核的两项发现，仅修改 supervisor.py、test_supervisor.py 及本报告。正常完成与显式 completed 恢复复用固定审核任务映射；developer 恢复为 needs_review 时，同一 queue 原子提交中去重登记 reviewer，不重置已有审核任务、不改角色、不把历史未知周期改为成功。已有审核任务按 ID 保留原状态；若其本身未知，仍须单独只读核对，不能借开发恢复放行。

English: This section describes the current follow-up and takes precedence over historical test records below. Only supervisor.py, test_supervisor.py and this report were changed for the two independent-review findings. Normal completion and explicit completed recovery share the fixed review-task mapping. Recovering a developer to needs_review atomically registers a deduplicated reviewer in the same queue commit, without resetting existing reviews, changing roles or converting unknown historical cycles into successes. Existing review tasks retain their state by ID; an unknown reviewer still requires separate read-only reconciliation.

中文：exclusive 现在在主异常传播时捕获锁删除 OSError，给原异常附注 LOCK_CLEANUP_FAILED 并重新抛出同一异常对象；queue/receipt 阶段附注保留。没有主异常时，锁删除失败继续向调用方报错。残留锁继续阻止派发，本轮没有添加自动解锁或删除用户锁的入口。临时文件清理仍保留原写入异常。

English: During primary-exception propagation, exclusive now catches lock-removal OSError, annotates the primary exception with LOCK_CLEANUP_FAILED and rethrows the same exception object, retaining queue/receipt stage notes. With no primary exception, lock-removal failure still propagates. A remaining lock continues to block dispatch; no automatic unlock or user-lock deletion entry point was added. Temporary-file cleanup still preserves the original write exception.

中文：新增 3 个测试方法，总计 22 个：四组固定 developer/reviewer 映射分别覆盖审核缺失和已有两种恢复分支，断言审核只登记一次、只派发 reviewer、developer 不重执行、历史周期不增加；queue 完成提交失败与 receipt 失败分别叠加锁删除失败，断言原异常对象身份、两个阶段附注、旧 queue 字节、权威状态、残留锁阻塞及 runner 调用次数为 1；另测无主异常的锁删除失败仍报错。原 dump/flush/fsync/replace 故障、未知结果隔离、receipt 按需修复及真实触发证据断言均保留，没有降低旧断言。

English: Three test methods were added, bringing the total to 22. All four fixed developer/reviewer mappings cover both absent and existing reviews, asserting single registration, reviewer-only dispatch, no developer rerun and no added historical cycles. Queue-completion and receipt failures are each combined with lock-removal failure, asserting primary-exception identity, both stage notes, unchanged queue bytes, authoritative status, orphan-lock exclusion and exactly one runner invocation. A separate test checks lock-removal failure with no primary exception still propagates. Existing dump/flush/fsync/replace injections, unknown-outcome quarantine, selective receipt repair and authentic-trigger assertions remain intact without weakened assertions.

中文：本轮实际验证仅有 git diff --check 通过及静态差异自检。尝试执行 Python312/python.exe -B -m unittest autonomy.test_supervisor -q 被系统以“拒绝访问”阻止，22 项测试均未在本轮运行；下文 19 项通过是历史记录，不是当前通过证据。未绕过访问控制或更换执行环境。本轮开发已写入但运行验证未完成，也未独立审核验收。CURRENT_STATUS.md 和 FILE_MANIFEST.md 启动检查未找到。

English: Current verification consists only of a passing git diff --check and static diff inspection. Running Python312/python.exe -B -m unittest autonomy.test_supervisor -q was blocked by system access denial; none of the 22 tests ran in this follow-up. The 19-test passes below are historical, not current evidence. No access-control bypass or alternate execution environment was used. Changes are written, but runtime verification and independent acceptance remain incomplete. Startup checks did not find CURRENT_STATUS.md or FILE_MANIFEST.md.

中文：未修改 process_job.py 或既有未提交文件，未触发真实代理、联网、采集、生产 DB、SMTP，未读取凭据、删除用户文件、自行提交或部署。风险仍包括空间预检、输出上限、异常进程清理及只读核对证据的可信性；本轮不证明历史故障已恢复或自主运行已恢复。下一步在获准可执行 Python 的环境运行全部 22 项离线测试，再独立审核。报告已自检双语、数量、未执行事项、风险、下一步及敏感信息；无真实客户数据或秘密。

English: process_job.py and pre-existing uncommitted files were not edited. No real agents, networking, collection, production DB, SMTP, credentials, user-file deletion, commits or deployment were used. Remaining risks include space preflight, output caps, exceptional process cleanup and trustworthy read-only reconciliation evidence. This follow-up establishes neither historical incident recovery nor autonomous-operation recovery. Next, run all 22 offline tests where Python execution is authorized, then obtain independent review. The report was checked for bilingual content, counts, non-executed work, risks, next steps and sensitive information; it contains no real customer data or secrets.

## 执行结果 / Results

中文：本次仅修改 `autonomy/supervisor.py`、`autonomy/test_supervisor.py` 并新增本报告。中断 running 租约、runner 超时、不完整输出、无效结果及执行异常均隔离为 `unknown`，标记 `outcome_unknown=true`，不自动重执行。旧版 failed/interrupted 周期关联的 queued/blocked 任务也保守隔离；attempts 较小或 needs_reassessment=false 均不能使未知结果放行。固定任务角色、互斥锁、真实触发证据规则和生产隔离保持。

English: This change only edits `autonomy/supervisor.py`, `autonomy/test_supervisor.py` and adds this report. Interrupted running leases, runner timeouts, incomplete output, invalid results and execution exceptions are quarantined as `unknown` with `outcome_unknown=true`, without automatic re-execution. Queued/blocked tasks associated with legacy failed/interrupted cycles are conservatively quarantined too. Low attempts or needs_reassessment=false cannot release unknown outcomes. Fixed task roles, exclusive locking, authentic-trigger evidence rules and production isolation remain intact.

## 提交边界 / Commit boundaries

中文：执行前先持久化 running 租约。执行后 queue 提交失败时保留原始异常并附注 `QUEUE_COMMIT_FAILED_OUTCOME_UNKNOWN`，停止该次派发，不生成虚假终态 receipt；磁盘旧 JSON 保持完整，其 running 租约在下一周期先隔离落盘。若 queue 提交成功但 receipt 失败，附注 `QUEUE_COMMITTED_RECEIPT_PENDING`；queue 为权威，后续仅修复缺失、损坏或内容不一致的 receipt，一致历史记录不重写。临时文件清理失败仅给原异常附注 `TEMP_CLEANUP_FAILED`，不覆盖主异常。异常正文不写入任务记录。

English: A running lease is persisted before execution. If the post-execution queue commit fails, the original exception is retained with `QUEUE_COMMIT_FAILED_OUTCOME_UNKNOWN`; dispatch stops and no false terminal receipt is created. The old JSON remains intact, and its running lease is durably quarantined on the next cycle. If queue commit succeeds but receipt creation fails, the exception is annotated `QUEUE_COMMITTED_RECEIPT_PENDING`. Queue remains authoritative; reconciliation repairs only missing, corrupt or inconsistent receipts and does not rewrite matching history. Temporary-file cleanup failures only annotate the primary exception with `TEMP_CLEANUP_FAILED`. Exception messages are not serialized into task records.

## 显式恢复协议 / Explicit recovery protocol

中文：`recover_unknown(runtime, task_id, readonly_check)` 是显式本地工程接口，cycle 不调用它，没有新增自动恢复 CLI。受信调用方必须以只读方式核查成果，返回 `read_only=true`、非空脱敏 evidence 及 resolution。`completed` 将 reviewer 标为 completed、developer 标为 needs_review；开发成果仍须独立审核，不表示审核已完成。`not_executed` 必须有证据确认未执行，才重新 queued，attempts 不重置、角色不改变。无法确认、部分执行、核对异常或缺少证据一律维持隔离。核对记录绑定原租约，不作为新失败租约的通行证。核对不改写历史周期为成功，因此不新增无人值守成功证据。

English: `recover_unknown(runtime, task_id, readonly_check)` is an explicit local engineering API, never invoked by cycle, with no new automatic recovery CLI. A trusted caller must inspect artifacts read-only and return `read_only=true`, nonempty sanitized evidence and a resolution. `completed` marks reviewers completed and developers needs_review; developer artifacts still require independent review and are not declared approved. `not_executed` must establish non-execution before requeuing, without resetting attempts or changing roles. Uncertainty, partial execution, checker exceptions or missing evidence leave quarantine intact. Reconciliation is bound to the original lease and cannot authorize a later failed lease. Historical cycles are not rewritten as successes, so recovery adds no unattended-success evidence.

## 验证与数量 / Verification and counts

中文：使用本地 Python 3.12 执行 `-B -m unittest autonomy.test_supervisor -q`，最终 19 项测试通过。合成有副作用 runner 计数验证超时、不完整结果、异常及四类完成提交故障恢复后调用次数仍为 1；dump/flush/fsync/replace 故障逐项验证旧 JSON 字节不变；叠加 unlink 故障验证主异常对象身份不变；receipt 故障验证 queue 已终态、不重跑、仅补缺失或不一致回执。显式无证据恢复被拒绝，确认未执行才可恢复。既有真实子进程树超时测试也通过，仅启动本地合成 Python 父子进程，没有真实代理或联网。

English: Local Python 3.12 ran `-B -m unittest autonomy.test_supervisor -q`; all 19 tests passed. Synthetic side-effect runner counters remain at one after timeout, incomplete-result, exception and four completion-commit fault recoveries. Dump/flush/fsync/replace injections verify byte-identical old JSON; concurrent unlink failure verifies primary-exception object identity. Receipt failure verifies terminal queue authority, no rerun and repair of only missing/inconsistent receipts. Evidence-free recovery is rejected; confirmed non-execution permits explicit recovery. The existing process-tree timeout test also passed using only local synthetic Python parent/child processes, with no real agent or networking.

## 未执行、风险与下一步 / Non-executed work, risks and next steps

中文：未修改 process_job.py、队列或生产状态，未启动真实代理、联网、采集、生产 DB、SMTP，未读取凭据、删除用户文件、自行提交或发布。工作区启动时已存在 process_job.py 修改及 lock_recovery.py/test_process_job.py 未跟踪文件，本次保留它们；测试使用当前工作区 process_job 实现，不能代表独立基线验收。空间预检、输出上限及异常进程清理仍属审查后续项。原子 replace 不提供外部副作用事务，也不证明断电持久性；磁盘持续不可写时无法持久化新分类，但原 running 租约仍禁止自动重跑。只读 callback 属受信工程边界，字段校验不能证明其真实只读或证据真实性；不得把任意自填 evidence 当作核对通过。独立审查、真实历史故障核对及生产验收尚未完成；下一步先独立复核最终差异与失败路径，再决定后续有界任务。开发完成不等于自主运行恢复。

English: No changes were made to process_job.py, runtime queue or production state. No real agents, networking, collection, production DB, SMTP, credentials, user-file deletion, commits or releases were used. The workspace already contained process_job.py modifications and untracked lock_recovery.py/test_process_job.py; these were preserved. Tests use the current workspace process_job implementation and do not establish acceptance against an independent baseline. Space preflight, output caps and exceptional process cleanup remain subsequent audit items. Atomic replace provides neither an external-side-effect transaction nor proven power-loss durability. Persistent storage failure prevents saving a new classification, but the original running lease still prevents automatic rerun. The read-only callback is a trusted engineering boundary: schema validation cannot establish actual read-only behavior or evidence authenticity, and arbitrary self-asserted evidence must not count as reconciliation. Independent review, historical incident reconciliation and production acceptance remain pending. Next, independently review the final diff and failure paths before selecting subsequent bounded work. Development completion does not establish autonomous-operation recovery.

中文：报告自检通过：双语、结果、数量、未执行事项、风险、下一步及敏感信息检查齐全；仅使用合成数据，无凭据或真实客户数据。

English: Report self-check passed for bilingual content, results, counts, non-executed work, risks, next steps and sensitive-information checks. Only synthetic data appears; no credentials or real customer data are included.


## 2026-10-20 未知结果隔离开发 / Unknown-outcome quarantine development

未知结果隔离开发完成，开发及父复核19项通过；独立审核待完成，整体未验收。父复核使用已提交cd9f454的process_job启动器，19项通过；预存process_job.py、lock_recovery.py、test_process_job.py三个文件SHA256未改变，不属于本轮提交。当前5项存储发现未独立验收关闭。下次真实心跳独立审核D-unknown-outcome-review；保留其他3份未提交改动，不合并未经审核的启动器。

Unknown-outcome quarantine development completed; developer and parent checks passed 19 tests; independent review pending, overall acceptance incomplete. Parent verification used the committed cd9f454 process runner and passed 19 tests. SHA256 values for the pre-existing process_job.py, lock_recovery.py and test_process_job.py remain unchanged; those files are excluded from this commit. None of the five storage findings is independently closed. Next genuine heartbeat independently reviews D-unknown-outcome-review; retain the three pre-existing changes and do not integrate the unreviewed runner.

08:57Z无执行回执，不计成功；10:55:53Z触发于12:54:48Z才启动，延迟7135秒，12:59:59Z完成。如实记录延迟，不作为准点两小时运行证明。累计成功任务5，历史两连续周期证明保留，最新两触发非连续成功，AUTONOMOUS_OPERATIONS_ACTIVE=false。未部署、未发信、未访问生产DB，指标UNKNOWN。

The 08:57Z trigger has no execution receipt and is not successful. The 10:55:53Z trigger started at 12:54:48Z after a 7135-second delay and finished at 12:59:59Z. This delay is recorded, not treated as evidence of punctual two-hour execution. Five tasks completed; the historical consecutive pair remains verified, the latest pair is not consecutive, and AUTONOMOUS_OPERATIONS_ACTIVE=false. No deployment, email sending or production DB access; metrics remain UNKNOWN.


## 2026-10-20 23:25 补修及父复核 / Follow-up and parent verification

两项恢复补修完成，父进程使用已提交启动器复跑22项测试通过；开发代理未运行测试，独立审核待完成。

Two recovery follow-up fixes implemented; parent rerun with the committed runner passed 22 tests. Developer could not execute tests; independent review remains pending.

触发 / Trigger: 2026-10-20T15:20:55.089Z; cycle `10e948fc-af43-462d-a53a-0d3edeeb0949`; execution 2026-10-20T15:21:58.004329+00:00 — 2026-10-20T15:24:21.798422+00:00.

下次真实心跳独立审核恢复后审核去重与主异常保留；其余存储发现继续保留，整体未验收。

Next genuine heartbeat independently reviews recovery review-deduplication and primary-error preservation; other storage findings remain open and overall acceptance is incomplete.

三份既有未提交文件哈希不变；无生产部署、采集、DB访问或发信，业务指标UNKNOWN。

Three pre-existing uncommitted file hashes are unchanged. No production deployment, discovery, DB access or sending; business metrics remain UNKNOWN.
