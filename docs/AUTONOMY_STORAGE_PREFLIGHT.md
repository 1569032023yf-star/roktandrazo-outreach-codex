# 空间预检 / Storage admission

未知结果及写入关闭补修限定审核通过；空间预检与双来源交接45项回归、21项独立审核通过；生产仍受通道及来源访问阻塞

Scoped unknown-outcome and write-close review passed; storage admission and discovery handoff passed 45 regressions and 21 independent checks; production remains blocked by channel and source access

检查runtime、工作树及TEMP实际路径最近存在目录，每项至少256MiB余量加16MiB提交预算。低空间或未知均在调用runner之前拒绝，不增加attempts；下次周期可重新检查，无副作用重跑。

Checks the nearest existing directory for runtime, worktree and TEMP, requiring 256MiB headroom plus 16MiB commit budget per target. Low or unknown space rejects before runner invocation without consuming attempts; subsequent checks are safe because no task executed.

这是只读检查，不是原子空间预留；无法消除检查后耗尽空间。磁盘满完成写入仍使用UNKNOWN隔离。先前测试两处夹具错误修复后45通过，独立范围21通过；其余输出和锁清理未验收。

This is a read-only check, not an atomic reservation; space can disappear afterward. Completion-write failure still uses UNKNOWN quarantine. After fixing two test-fixture issues, 45 regressions and 21 independent scoped checks passed. Output and lock-cleanup acceptance remains incomplete.
