# 迟到回执与重建适配器独立审核 / Independent late-receipt and adapter-reconstruction review

结论 / Verdict: PASS_FOR_OFFLINE_RESTART_AND_CLOCK_FAULT_TESTS

范围 / Scope: `test_single_slot_adapter.py` 新增两个测试；为理解断言只读检查现有 adapter 实现。 / Two added tests in test_single_slot_adapter.py; existing adapter implementation inspected read-only to assess assertions.
审核时 HEAD / HEAD during review: `cb9b876bdf426498febbf2ca8844828f67390b13`。新增测试当时属于工作树 diff；不宣称已包含于该提交。 / The new tests were working-tree changes at review time, not claimed to be contained in that commit.
工作树测试文件 SHA256 / Working-tree test file SHA256: `bfbf3c332f9ff70aa6c51bcaf7c78ebc72658a884078a007e30853448af2ac1b`。

## 实际测试 / Execution

`python -B -m unittest test_single_slot_adapter -q`: 15 tests passed, 2.374 seconds.

## 审核结果 / Findings

未发现新增测试范围内的阻断缺陷。 / No blocking defect found in the added-test scope.

- 迟到回执测试注入单调时间 1→4，超过预留 wall_seconds=1；返回 UNKNOWN_RECONCILE_ONLY。随后从相同 SQLite 路径构造新的 DurableSlots/GrowthLedger 和 adapter，再次 execute 仍为 UNKNOWN，backend.calls 保持1。 / The late-receipt test injects monotonic time 1→4, exceeding reserved wall_seconds=1, yielding UNKNOWN_RECONCILE_ONLY. New DurableSlots/GrowthLedger and adapter instances reopen the same SQLite paths; a second execute remains UNKNOWN and backend.calls remains one.
- 显式对账前检查 reservation 仍为 reserved；已签名 fixture 回执使 reconcile 返回 COMPLETED，再次对账 budget_result=DUPLICATE，effects 只有一次。 / Before explicit reconciliation the reservation remains reserved. Signed fixture receipts produce COMPLETED, repeated reconciliation returns budget_result=DUPLICATE, and effects occur once.
- NaN、正无穷、倒退到0及 bool 四类结束时钟各使用独立临时账本；每例断言 UNKNOWN、持久 slot 状态 unknown、backend.calls=1，随后调用显式 reconcile。 / NaN, positive infinity, backward zero and bool completion clocks each use isolated temporary ledgers; each asserts UNKNOWN, persisted unknown slot state and one backend call, followed by explicit reconciliation.
- 临时资源通过 doCleanups 释放；测试不调用真实采集后端。 / Temporary resources use doCleanups; no real collection backend is invoked.

## 证据边界 / Evidence limits

重建发生在同一进程、同一仍持有的排他锁内，backend fixture 对象及其回执也保留。因此证明对象重建与数据库重开后的持久重放保护，不证明完整进程重启、Windows 重启、跨登录、锁重新获取或回执外部持久化。 / Reconstruction occurs in one process under the same held exclusive lock; the backend fixture and its receipts survive. This proves persistence-backed replay prevention across object reconstruction/database reopening, not full process restart, Windows reboot, cross-login operation, lock reacquisition or external receipt persistence.

时钟故障测试未单独断言每次 reconcile 返回值，成功重对账与幂等性的显式断言来自迟到回执测试。 / Clock-fault cases do not separately assert each reconciliation return; explicit successful/idempotent reconciliation assertions come from the late-receipt test.

没有新增运行时取消协议或硬超时实现；迟到结果拒绝不等于终止后端。测试覆盖不代表取消协议、生产后端、U1 整体或生产验收完成。 / No runtime cancellation protocol or hard timeout was added; rejecting late results does not terminate a backend. Coverage does not establish cancellation protocol completion, production backend readiness, overall U1 completion or production acceptance.
