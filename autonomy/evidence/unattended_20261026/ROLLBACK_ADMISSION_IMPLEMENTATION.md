# 回滚计划离线准入 / Offline rollback-plan admission

## 结果与合同 / Result and contract
新增纯判定器 autonomy/rollback_admission.py，复用 EvidenceConsumer 验证 rollback_readiness 签名、来源身份、唯一 Inventory 与新鲜度。调用方须独立提供可信 expected，精确绑定发布 SHA256、保留账本 SHA256/schema、旧执行器 SHA256、前后 authority epoch、身份及排他锁 ID；不得从待验信封直接复制 expected。
The pure evaluator verifies signed rollback_readiness evidence through EvidenceConsumer. Independently trusted caller context binds release, preserved ledger, executor hashes, ledger schema, previous/new authority epochs, principal and exclusive lock. Expected values must not be derived from the untrusted envelope.

全部字段严格类型匹配，拒绝 bool 代替整数；必须批准身份、唯一 Inventory、停止派发、排空进程树、正式对账完成、保留账本、旧执行器支持现账本/schema/新 epoch、排他锁证据。claimed/running/unknown slot 与 unknown/reserved/overrun budget 必须明确为整数零。恢复旧数据库必须明确 false；缺失、未知、不一致、旧 epoch 或未清副作用拒绝。
Strict type checks reject bool/integer substitution. Required facts cover approved identity, sole Inventory, stopped dispatch, drained process tree, formal reconciliation, ledger preservation, executor compatibility and exclusion. Claimed, running and unknown slots and unknown/reserved/overrun budgets must explicitly equal integer zero; restoring an old database must explicitly be false. Missing, unknown, mismatched, stale-epoch or unresolved evidence denies admission.

## 测试与数量 / Tests and counts
python -B -m unittest test_rollback_admission test_host_preparation -q：18 项通过，其中新增 9 项，包含逐字段缺失子测试、签名篡改、错误 kind、指纹/epoch 不符、未清状态、类型混淆、不兼容、旧数据库恢复、新鲜度与成功路径。
18 tests passed, including 9 new tests with missing-field subtests, tampering, wrong kind, binding/epoch mismatch, unsettled effects, type confusion, incompatibility, database restore, freshness and success.

## 未执行与风险 / Non-actions and limits
所有输出 allow_dispatch 永远 false；成功仅 allow_rollback_plan，不能作为执行许可证。签名只验证可信来源的声明，不证明真实 OS 已排空或独占；本模块不调用 OS、网络、生产数据库或执行器，也不安装回滚入口。状态：开发与定向测试完成，独审 PENDING，发布/部署/生产验收未完成。固定原因码不回传异常文本、身份、哈希或客户字段。
allow_dispatch is always false; success admits a plan only, never execution. Signatures establish attributable assertions, not actual OS drain/exclusion truth. No OS, network, production database or executor access, and no execution entry point is created. Development and targeted tests complete; independent review pending; release, deployment and production acceptance unproven. Fixed reason codes do not echo exception text, identities, hashes or customer fields.

## 下一步与自检 / Next step and self-check
由父任务独审精确源码与合同，再决定集成；未改 queue/manifest、未提交。报告自检：中英双语、结果/数量/风险/未执行/下一步齐全；仅虚构测试密钥，无生产秘密。
Parent task should independently review the exact code and contract before integration. No queue/manifest edits or commit. Report self-check passes bilingual content, outcomes, counts, risks, non-actions and next steps; fixtures contain synthetic test keys only, no production secrets.
