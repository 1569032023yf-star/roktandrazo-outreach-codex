# 结算失败恢复栅栏独立审核 / Independent settlement recovery fence review

独审封签状态：CONFIRMED。Reviewer 已恢复、复核源码与测试哈希未变，并重新执行16项测试通过（2.451秒）。前次执行记录真实有效，本次正式确认限定结论。 / Review seal: CONFIRMED. Reviewer resumed, verified unchanged source/test hashes and reran all 16 tests successfully (2.451 seconds). Prior execution records are valid; the scoped verdict is now confirmed.

结论 / Verdict: PASS_FOR_OFFLINE_SETTLEMENT_FENCE_FIX

固定提交 / Fixed commit: `ec62af049c903f83eb7c593834dd7d8a8a61946c`。
范围 / Scope: `SingleSlotAdapter.reconcile` 调整结算与 verified_closed 顺序，以及新增结算存储失败测试。 / Ordering of budget settlement and verified_closed in SingleSlotAdapter.reconcile, plus the new settlement storage failure test.

## 实际验证 / Executed validation

- `python -B -m unittest test_single_slot_adapter -q`: 16 tests passed, 2.933 seconds.
- 独立补充注入：调用真实 GrowthLedger.settle，只在其事务 before_commit 阶段抛 OSError；确认 slot completed、reservation reserved、UNKNOWN_RECONCILE_ONLY、锁保留及 backend.calls=1。 / Independent additional injection calls the real GrowthLedger.settle and raises OSError only at its transaction before_commit stage; confirmed completed slot, reserved budget, UNKNOWN_RECONCILE_ONLY, retained lock and one backend call.

## 审核结论 / Findings

本范围未发现阻断缺陷。之前 slot 已提交完成但 budget.settle 抛异常时，verified_closed 已提前写入；本修改将该写入移至 settle 返回之后，因此未确认结算不会清除恢复栅栏。 / No blocking defect found in scope. Previously verified_closed could already be written when a completed slot was followed by a settlement exception. Moving that write after settle returns prevents unacknowledged settlement from clearing the recovery fence.

现有代码仍要求已验证的 drained 回执，检查其他未完成 slot；正常结算/重复回执路径继续通过。执行异常返回 UNKNOWN，slot 的已完成状态不会被改回可执行；保留的锁要求后续正式恢复核对。 / Existing verified drained receipts and other unresolved slot checks remain. Normal settlement and duplicate receipt paths still pass. Execution failure returns UNKNOWN without making a completed slot dispatchable; the retained lock requires subsequent formal recovery reconciliation.

新增测试只调用一次 execute，因此 calls=1 证明没有隐式二次调用，不单独证明故障后再次 execute 的行为；已有相关重放测试仍通过。 / The new test calls execute once, so calls=1 proves no implicit second call, not independently the behavior of another execute after this failure. Existing replay tests still pass.

## 审核字节 / Reviewed bytes

Windows 文件 SHA256 / Windows file SHA256:
- `autonomy/single_slot_adapter.py`: `9a3c2a57f19954c7b46726e2b854588d9651855087a8bf02c0dfb8f927ffbd3c`
- `test_single_slot_adapter.py`: `b5387c55258dd56e726679554a3b9481ff8b0606221ed7f4ba0c6eb3dcd9a444`

## 边界 / Limits

仅在临时隔离 SQLite 与 synthetic backend 验证，未操作生产数据库或真实采集。不是跨库原子事务、硬取消协议、真实进程重启、生产恢复流程或生产验收的完成证明；未升级总体 U1 或发布/部署/业务增长状态。 / Verified only with temporary isolated SQLite and a synthetic backend, with no production database or collection. This does not establish cross-database atomicity, hard cancellation, real process restart, production recovery procedure or production acceptance, and does not upgrade overall U1 or release/deployment/business-growth status.

## 旧实现反证 / Prior implementation negative control

Reviewer 已从 `ec62af0^:autonomy/single_slot_adapter.py` 读取 Git 字节，在独立 Python 进程内替换测试引用的类（未修改磁盘源码），运行新增结算失败测试。结果准确出现一项预期失败 `RuntimeError not raised`、零 errors；新实现16项通过。因此新测试实际识别旧版提前释放恢复栅栏的行为。 / Reviewer loaded Git bytes from ec62af0^:autonomy/single_slot_adapter.py and substituted the test class reference inside a separate Python process without modifying source files. The new test produced exactly one expected failure, RuntimeError not raised, and zero errors. The new implementation passes all 16 tests, demonstrating that the test detects the previous premature fence release.
