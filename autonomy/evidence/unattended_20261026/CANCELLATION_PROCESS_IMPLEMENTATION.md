# 取消意图日志进程故障验证 / Cancellation intent process-fault validation

## 结果与数量 / Results and counts
新增 3 项 CancellationProcessTests，定向运行 python -B -m unittest test_single_slot_adapter.CancellationProcessTests -q 全通过（1.041 秒）。运行源码没有修改。
Three new subprocess tests passed in 1.041 seconds. Runtime source code is unchanged.

四个独立 Python 进程等待就绪栅栏后，对同一临时 SQLite journal 同一身份/绑定并发 reserve，结果恰好一个 RESERVED_RECONCILE_ONLY、三个 DUPLICATE_RESERVED；数据库最终一行且 integrity_check=ok。after_commit 中 os._exit(73) 后，新进程返回 DUPLICATE；before_commit 中 os._exit(73) 后，新进程可记录一次意图，再次重开为 DUPLICATE。
Four independent Python processes synchronize on a readiness gate and reserve the same temporary journal identity/binding. Exactly one reservation and three duplicates result, with one row and successful integrity check. An os._exit(73) after commit is followed by duplicate recognition in a new process. Exit before commit allows one fresh intent record, then duplicate recognition on another reopen.

## 隔离与限制 / Isolation and limits
固定 Python worker 源码，shell=false、stdin=DEVNULL、Windows 隐藏窗口；只传临时路径与固定故障阶段。就绪等待 10 秒，进程结果等待 15 秒；超时 kill 并 communicate 回收，自建子进程由 cleanup 收回，最多四个同时存活。各测试组串行，无 stdin multiprocessing。
Workers use fixed Python source, no shell or stdin, hidden Windows windows, temporary paths and fixed fault phases. Readiness has a ten-second limit; result collection has a fifteen-second limit. Timed-out fixture children are killed/reaped and cleanup handles all owned processes. At most four run concurrently; groups run serially without stdin multiprocessing.

allow_cancel_dispatch 与 production_execution 均验证为 false。退出发生在 SQLite 提交钩子，验证的是软件进程退出恢复，不是断电或硬盘硬件持久性。没有 backend.cancel_once、生产取消、采集、预算退款、清锁或网络操作；不证明 U1 生产验收。
Both dispatch and production execution flags remain false. SQLite commit-hook process exits test software crash recovery, not power-loss/hardware durability. There is no backend cancellation, production cancellation, collection, refund, lock release or network operation; this does not establish U1 production acceptance.

## 状态和下一步 / Status and next steps
定向测试完成，独审待父任务执行；未提交、未改运行源码、共享清单或队列。下一步审查精确测试和报告；是否补其他回归由父任务决定。双语报告自检通过，包含结果、数量、未执行、风险、下一步；无真实秘密或客户数据。
Targeted validation complete; independent parent review pending. No commit, runtime-source, manifest or queue changes. Next: review exact tests/report and let parent determine any broader regression. Bilingual report self-check includes outcomes, counts, non-actions, risks and next steps without real secrets/customer data.
