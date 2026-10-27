# 回归进度独审 / Regression progress review

固定提交 / Reviewed commit: `488d4393f34ae4348bc1e4b8825e657dced523ea`。
结论 / Verdict: **CHANGES_REQUIRED_FOR_PROGRESS_SEMANTICS**。

轻量独立执行test_comparable_progress：1项通过，0.001秒。每次stopTest写入一行并flush，进度不含失败traceback；新增运行在discover之前删除旧result.json，若suite异常中断则不会写新result，静态上修复了旧完成文件被误认为新完成结果的问题。 / The lightweight test passed independently: one test in 0.001 seconds. Each stopTest writes and flushes a row without failure tracebacks. A new attempt removes result.json before discovery; an interrupted suite does not produce a new result, preventing stale completion reuse.

## 发现 / Finding

**P2：stopTest不等于测试完成。** unittest在KeyboardInterrupt传播时仍在finally调用stopTest。独立单进程最小反例在test方法抛KeyboardInterrupt，实际journal仍输出`{"completed_test":"__main__.Interrupted.test_interrupt","run":1}`。该测试未产生成功/失败/error等正常结果，标为completed_test不准确，尤其不能用于日后断点跳过。 / unittest invokes stopTest from a finally block even when KeyboardInterrupt propagates. An independent test raising KeyboardInterrupt emitted a completed_test row despite having no normal terminal outcome. This is not a reliable completed-test set and must never drive resume skipping.

建议改名stopped_test并明确outcome=UNKNOWN，或追踪终态回调后才标completed；保留中断测试进度但不得称已完成。增加KeyboardInterrupt反例。 / Rename the record to stopped_test with an explicit unknown outcome, or track terminal callbacks before labeling it completed. Add a KeyboardInterrupt counterexample.

本发现不表示中断后生成了result.json；目前main不捕获该异常，仍会跳过最终结果写入。 / This finding does not imply that interruption creates result.json; main still propagates the exception and skips final result creation.

## 边界 / Boundaries

flush只保证Python缓冲送往OS，不等于fsync断电持久化；本工具不支持跨进程resume。partial progress不能替代完整结果及失败/错误ID集合。既有测试只覆盖成功/失败的journal与flush，不动态覆盖main的旧result删除逻辑；本次对删除位置进行了静态核验。 / Flush drains Python buffers to the OS and does not guarantee power-loss durability. Cross-process resume is unsupported; partial progress is not full-suite acceptance. The existing test covers normal success/failure journaling and flushing; stale-result deletion was reviewed statically.

未运行全suite或多进程，未改实现、未提交或触碰生产。 / No full suite or multiprocessing run, implementation change, commit or production access was performed.

## 最终修复复审 / Final fix re-review

固定提交 / Final reviewed commit: `b69214dcbe86a7c77a167dbf665649fa0fda08f5`（含57b4a41中断清理测试 / includes interruption-cleanup testing）。
最终结论 / Final verdict: **PASS_FOR_BOUNDED_REGRESSION_PROGRESS**，上述P2发现已修复。字段改为stopped_test，文档明确中断结果可能UNKNOWN，不再声称测试已完成。 / The P2 finding is resolved: stopped_test replaces completed_test, with explicit documentation that interruption may leave the outcome unknown.

独立执行test_comparable_progress：**3 tests passed，0.007秒，退出0**。正常停止记录每条flush、真实测试KeyboardInterrupt仅记录stopped_test、discovery中断删除旧result且journal为空均通过。 / Independent execution: **3 tests passed in 0.007 seconds, exit 0**. Verified per-record flushing, a real interrupted test producing only a stopped record, and interrupted discovery removing stale results while leaving an empty journal.

原发现关闭；仍不支持跨进程resume，stopped_test不能作为跳过已完成测试集合，partial journal不得当全量结果，flush不声称断电持久化。未跑全suite或多进程，未提交。 / Finding closed. Cross-process resume remains unsupported; stopped IDs are not a completed-test skip set, partial journals are not full results, and flush is not power-loss durability. No full or multiprocessing suite ran; no commit was made.
