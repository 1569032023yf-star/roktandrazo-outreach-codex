# 取消意图多进程测试独立审核 / Independent cancellation-intent multiprocess test review

结论 / Verdict: PASS_FOR_OFFLINE_JOURNAL_PROCESS_TESTS

范围 / Scope: `test_single_slot_adapter.py` 的 CancellationProcessTests 三项新增测试及固定 worker。 / Three new CancellationProcessTests and their fixed worker source.
审核文件 Windows SHA256 / Reviewed Windows file SHA256: `5a7f3ba91d6e348f93e7ff67e35af42b1c88f20bf2eecf0a8964b7cca2d6c4d9`。

## 实际执行 / Execution

`python -B -m unittest test_single_slot_adapter.CancellationProcessTests -q`: 3 tests passed, 1.223 seconds.

## 审核结论 / Findings

本范围未发现阻断缺陷。 / No blocking defect found in scope.

- 四个真实 Python 子进程经过 ready/gate 协调后争用相同临时 SQLite journal；确认仅一次 RESERVED 与三次 DUPLICATE，并检查唯一行及 integrity_check。 / Four actual Python subprocesses synchronize through ready/gate files and contend on one temporary SQLite journal; assertions require one RESERVED and three DUPLICATE outcomes, one row and successful integrity_check.
- before_commit 与 after_commit 使用 os._exit(73)，不经过普通异常清理；新进程分别首次记录或识别已提交记录，再确认唯一行。 / before_commit and after_commit use os._exit(73), bypassing normal exception cleanup; subsequent processes respectively record the rolled-back intent or recognize the committed intent, with one-row verification.
- 固定 sys.executable、固定 worker、shell=False、DEVNULL stdin，Windows 无窗口启动；参数仅临时夹具路径与固定阶段。 / Fixed sys.executable and worker source, shell=False, DEVNULL stdin and hidden Windows creation; arguments contain temporary fixture paths and a fixed fault phase.
- worker gate等待与父进程ready等待各有10秒界限，communicate有15秒界限及超时kill/reap；cleanup先处理已登记子进程，再移除临时目录。 / Worker gate and parent readiness waits each have ten-second bounds; communicate has a fifteen-second bound with timeout kill/reap. Cleanup processes registered children before temporary-directory removal.

## 边界 / Limits

并发 gate 不保证四个事务真正同时进入 SQLite，只证明四个独立进程在协调竞争场景下结果一致。os._exit 模拟进程突然退出，不是断电、内核崩溃或磁盘故障。 / The gate does not guarantee four simultaneous SQLite transactions; it establishes consistent results among four independently coordinated contenders. os._exit models abrupt process exit, not power loss, kernel crash or disk failure.

测试直接调用 journal.reserve，使用 protected=() 与固定 synthetic identity/binding；没有运行 adapter 签名/锁/claim/预算全链，也没有真正取消、退款、生产 API 或正式 Inventory。before_commit 后允许重新记录仅因为没有取消 dispatch。 / Tests directly call journal.reserve with protected=() and synthetic identity/binding. They do not exercise the adapter signature/lock/claim/budget chain, actual cancellation, refund, production APIs or formal Inventory. Recording after a before_commit exit is safe here because no cancellation dispatch occurs.

测试导入工作树代码，未使用 -I 或生产依赖镜像；输出捕获并非内存硬上限。子进程只执行固定 worker，无孙进程；cleanup不是通用进程树终止协议。 / Tests import checkout code without -I or a production dependency image; captured output has no hard memory cap. Workers are fixed and create no descendants; cleanup is not a general process-tree termination protocol.

本审核只认可 journal primitive 的离线多进程持久化与去重测试，不扩大为 adapter 全流程跨进程验收、取消完成或生产验收。Reviewer 未改源码、清单、队列或提交。 / Approval is limited to offline journal primitive multiprocess persistence/deduplication tests, not end-to-end adapter cross-process acceptance, completed cancellation or production acceptance. Reviewer changed no implementation, manifest or queue and created no commit.

测试固定提交 / Pinned test commit: `642eaf6`。固定后文件 SHA256 已复核，与上述字节一致；运行源码未因本次测试增量改变。 / File SHA256 was rechecked after pinning and matches the reviewed bytes; runtime source is unchanged by this test-only increment.
