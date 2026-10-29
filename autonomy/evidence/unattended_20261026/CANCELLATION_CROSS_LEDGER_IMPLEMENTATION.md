# 取消意图跨账本故障验证 / Cancellation-intent cross-ledger fault validation

结果 / Results: 新增 2 项测试，其中 journal 成功 ACK 与提交 ACK 丢失为两个独立临时数据库子场景。运行真实 SQLite，取消意图已持久化后，真实 GrowthLedger.settle 内 before_commit 故障回滚预算结算；slot 已 completed，但预算仍 reserved、charged 保持完整原预留、receipt_hash 未提交，原锁 tree_state=unverified。重复 execute 不调用 backend。恢复同一签名终态对账后才更新 settled 和 signed actual；journal 原行完全不变。
Two tests were added, including separate temporary-database cases for journal success and lost commit acknowledgement. A real before_commit fault inside GrowthLedger.settle rolls back budget settlement after intent persistence. Slot completion may already be committed, but the original reservation/charge remains, its receipt hash is uncommitted, and lock tree_state remains unverified. Repeated execute does not call the backend. Recovery with the same signed terminal receipts settles the budget; journal rows remain unchanged.

测试还确认原 claim 已 completed 后，新的取消意图被拒绝且不会创建 journal 文件。所有已返回 journal 结果 allow_cancel_dispatch=false，backend.calls=1。使用零 actual 的签名回执，与非零预留作对照，使提前退款可被断言发现。
Completed claims reject new cancellation intents without creating a journal file. Returned journal results keep allow_cancel_dispatch=false; backend calls remain one. Signed zero-actual receipts versus nonzero reservations make premature refunds observable.

精确命令 / Exact command:
`python -B -m unittest test_single_slot_adapter.SingleSlotTests.test_cancel_journal_then_settlement_failure_and_recovery test_single_slot_adapter.SingleSlotTests.test_completed_claim_cannot_create_cancel_intent -q`
结果 / Result: 2 tests passed, 见最终定向输出 / see final targeted output.

风险与未执行 / Risks and non-actions: 这是原执行预算的故障恢复验证，取消本身成本尚未预留，不能声称取消费用闭包。没有真实取消 backend、生产/网络访问、强杀、退款 API、清锁入口或跨库原子事务。测试不代替 U1 生产验收。初始测试曾在预算预读事务即触发故障，现已改为只在真实 settle 事务启用 before_commit 注入；最终命令通过。
This tests recovery of the original execution budget only. Cancellation costs are not reserved, so cancellation-cost closure is unproven. No real cancellation backend, production/network access, process termination, refund API, lock-release entry point or cross-database atomic transaction is introduced. Initial test injection hit a preliminary budget-read transaction; the final version activates the fault only inside the real settle transaction and passes.

下一步及状态 / Next step and status: 定向测试完成，父任务独审待执行；仅修改测试与本报告，未改运行源码/清单/队列，未提交。由主线串行组合验证并固定 SHA。报告中英双语、结果/数量/风险/未执行/下一步齐全，无生产秘密。
Targeted tests complete; independent parent review pending. Only tests and this report changed; no runtime, manifest, queue or commit changes. Parent performs serial combined validation and pins the SHA. Bilingual report self-check includes outcomes, counts, risks, non-actions and next steps without production secrets.

恢复栅栏 / Recovery fence: 预算结算失败后显式断言锁 tree_state=unverified，合法签名对账完成后才为 verified_closed。 Tests explicitly verify unverified after failed settlement and verified_closed only after successful signed reconciliation.
