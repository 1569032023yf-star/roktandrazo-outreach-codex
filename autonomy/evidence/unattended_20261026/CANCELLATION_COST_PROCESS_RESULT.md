# 取消费用进程退出证据 / Cancellation-cost process-exit evidence

中文：固定测试提交 `2e7900bbd97e60c61f4bdb2104282fafd1282f99`；运行源码及候选清单仍固定 `9b28eb9cfe78bdc1bb5fffe42f07560d6fa94a30`，没有生产源码/包变更。新增6项测试：5项真实子进程测试及1项旧意图升级冲突合同。

English: Tests pinned at `2e7900bbd97e60c61f4bdb2104282fafd1282f99`; runtime/manifest remain pinned at `9b28eb9cfe78bdc1bb5fffe42f07560d6fa94a30`. No production-source/package change. Six added tests comprise five real child-process tests and one legacy-intent upgrade conflict contract.

中文：子进程分别在真实GrowthLedger预留提交前/后、CancellationJournal提交前/后调用os._exit(73)，新子进程重开SQLite继续同一签名费用请求；每次都检查预算state、amount=charged、claim哈希、意图行数及SQLite integrity_check。预留提交前退出不留下费用行；之后三种退出均保留完整费用，journal提交后退出还保留原意图。重启只在不存在费用行时预留一次，其余NO_REPLAY；意图存在时DUPLICATE_RESERVED。原父进程adapter最后复核返回DUPLICATE_RESERVED、预算行逐项不变、backend调用数仍1；原执行终态对账后取消费用继续reserved。

English: Children call os._exit(73) before/after the real GrowthLedger reservation commit and CancellationJournal commit. A fresh child reopens SQLite using the same signed request. Assertions check budget state, full amount=charged, claim hash, intent counts and SQLite integrity. Pre-reservation-commit exit leaves no cost row; the other three retain full costs, and post-journal-commit exit also retains intent. Restart reserves only when absent, otherwise NO_REPLAY; persisted intent returns DUPLICATE_RESERVED. The parent adapter then returns DUPLICATE_RESERVED with unchanged budget rows and one original backend call. Original-run reconciliation leaves cancellation costs reserved.

中文：四个真实子进程同时竞争同一费用及意图：费用结果1次RESERVED_NOT_DISPATCHED+3次NO_REPLAY，意图结果1次RESERVED_RECONCILE_ONLY+3次DUPLICATE_RESERVED；最终预算2行（原执行+取消费用），意图1行。所有worker采用shell=False及Windows隐藏窗口标志，20秒超时和退出清理；输入仅为临时路径与合成签名，无网络或生产访问。

English: Four real children contend for identical cost/intent: one RESERVED_NOT_DISPATCHED plus three NO_REPLAY for costs, and one RESERVED_RECONCILE_ONLY plus three DUPLICATE_RESERVED for intent. Final counts are two budget rows (original execution plus cancellation) and one intent. Workers use shell=False, hidden Windows creation flags, a20-second timeout and cleanup. Inputs are temporary fixture paths/synthetic signatures only, without network or production access.

中文：旧版本无费用意图先落盘，再两次请求新费用绑定：均明确CANCEL_REQUEST_CONFLICT；旧journal各字段保持不变、新费用仅一条且完整reserved、不自动退款；backend仍调用1次。此合同仅确认保守拒绝，尚未实现旧意图升级迁移或自动释放孤立预留。

English: Persisting a legacy cost-free intent then requesting the new binding twice produces CANCEL_REQUEST_CONFLICT both times. Every legacy journal field remains unchanged, with one fully reserved cancellation cost and no automatic refund; the backend call count stays one. This proves conservative rejection only, not migration or automatic orphan-reservation release.

中文：实际执行：`python -B -m unittest test_cancellation_cost_process -q`，5项通过（3.313秒）。最终`python -B -m unittest test_single_slot_adapter test_durable_slots test_growth_ledger test_ledger_evidence test_cancellation_cost test_cancellation_cost_process -q`，84项通过（21.158秒）；git diff --check通过。本轮无运行实现变化，未重复完整回归或固定包导入；之前2项包导入仅继续适用于固定9b28eb9，不扩大测试结论。

English: The five child-process tests passed in3.313s. The final combined command above passed84 tests in21.158s; git diff --check passed. With unchanged runtime, full regression and pinned-import tests were not repeated; prior two import tests remain scoped to9b28eb9 and are not broadened.

中文：边界：父进程持有原运行锁，退出的是费用/journal工作子进程；不是完整adapter进程死亡、父宿主死亡、换锁接管、掉电或无人登录验收。测试中原执行UNKNOWN由真实fixture backend确认丢失产生，最后用签名原执行回执对账；没有伪造锁清理。重新阅读候选与最终测试差异已完成作者复核，独立审核仍PENDING，不能以本轮测试替代。allow_cancel_dispatch=false及生产派发关闭。

English: The parent retains the original runtime lock; only cost/journal workers exit. This does not prove whole-adapter/parent-host death, changed-lock takeover, power loss or login-free acceptance. Original UNKNOWN comes from a lost synthetic backend acknowledgement and is reconciled with signed original receipts, without fabricated lock cleanup. Author review of candidate/final test diffs is complete; independent review remains PENDING and is not replaced by these tests. Cancellation and production dispatch remain disabled.

中文：下一项：独立审核固定9b28eb9运行源码及2e7900b测试，继续离线设计并验证完整宿主死亡后的只读对账/换锁拒绝合同，旧意图与孤立费用只通过完整签名证据处理。没有生产采集、DB写入、SMTP、部署、配置/调度/配额变更或新增Issue通道/重复backend请求。报告无凭据或客户数据。整体U1开发完成、发布、部署及生产验收false，增长UNKNOWN。

English: Next: independent review of runtime9b28eb9 and tests2e7900b, then offline whole-host-death read-only reconciliation/changed-lock rejection contracts. Legacy intents and orphan costs require fully signed evidence. No production collection, DB writes, SMTP, deployment, configuration/scheduler/quota change, new Issue channel or duplicate backend request occurred. Reports contain no credentials/customer data. Overall U1 completion/release/deployment/production acceptance remain false; growth UNKNOWN.
