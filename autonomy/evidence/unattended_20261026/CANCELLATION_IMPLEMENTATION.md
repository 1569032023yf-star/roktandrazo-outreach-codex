# 持久取消意图准入 / Durable cancellation-intent admission

## 结果与合同 / Result and contract
新增 CancellationJournal 与 reserve_cancellation，只记录取消意图，不派发取消。默认没有 journal 配置即拒绝。offline_cancel_request 签名绑定原 Inventory/slot/epoch/owner/run/request、claim 哈希、runtime/backend/账本路径、原锁及 journal 路径身份、固定取消版本和离线 scope；核对当前 slot 尚未结案及 reservation 的 claim/binding。默认不需要 backend 取消能力，因为不调用 backend。
CancellationJournal and reserve_cancellation record intent only and reject missing configuration. Signed offline_cancel_request binds Inventory, slot, epoch, owner, run, request, claim hash, runtime/backend/ledger paths, original lock, journal path and fixed offline cancellation protocol. Current unresolved slot and reservation bindings must match. No backend cancellation capability is assumed or invoked.

独立 SQLite schema/version 精确匹配，不修改 slots/growth schema。BEGIN IMMEDIATE、synchronous=FULL，先持久记录唯一取消身份；同身份同绑定返回 DUPLICATE_RESERVED，不同绑定明确 CONFLICT。提交前后存储异常统一 UNKNOWN_RECONCILE_ONLY，不将 ACK 丢失视为没有写入。resolved path 与 samefile 防止 journal 和 slots/budget/锁文件别名。
A separate exact-version SQLite schema uses BEGIN IMMEDIATE and synchronous=FULL. Identical identities/bindings deduplicate; conflicting bindings reject. Storage failures before or after commit return UNKNOWN, never an assertion that nothing was written. Resolved paths and file identity checks reject aliases to slot/budget/lock files.

## 测试 / Tests
python -B -m unittest test_single_slot_adapter -q：26 项通过，新增 4 项；包括真实临时 SQLite commit ACK 丢失、重开重复、提交前失败、冲突、schema 拒绝、硬链接别名、签名/版本/claim/锁绑定拒绝、UNKNOWN slot 与 reserved budget 保留。
26 tests passed, including four new tests covering real temporary SQLite commit-ack loss, reopen deduplication, precommit failure, conflicts, schema mismatch, hardlink aliases, signature/version/claim/lock mismatch and preserved UNKNOWN slots/reserved budgets.

## 未执行与风险 / Non-actions and risks
allow_cancel_dispatch 始终 false，生产执行 false；取消意图记录不表示请求已发给 backend，更不表示取消成功。没有 cancel_once、timeout/强杀或取消 ACK 处理；不能声称这些生产能力已实现。跨 ledger 核对非原子，路径检查不能替代受保护目录 ACL，因此这些观测仅用于意图日志，不能提供取消派发许可。未清锁、退款、修改 slot、自动重放或恢复旧 DB；现有独立签名终态对账才可解除 fence。
Cancel dispatch and production execution remain false. Recorded intent does not mean a backend request or successful cancellation. No cancel_once, forced termination, cancellation timeout or ACK handling exists. Cross-ledger checks are not atomic and path checks do not replace protected-directory ACLs; this journal cannot authorize dispatch. No lock release, refund, slot mutation, replay or stale database restore occurs. Existing signed terminal reconciliation remains necessary.

## 状态与下一步 / Status and next steps
本范围开发/定向测试完成；父任务独审待完成；未提交、未改共享清单/queue、未触及生产或网络。后续必须先设计取消预算、原锁及跨账本 TOCTOU 合同，再考虑持久取消派发。报告自检：中英双语、结果/数量/风险/未执行/下一步齐全，无真实秘密。
Scoped development/tests complete; parent review pending. No commit, shared manifest/queue change, production or network access. A cancellation budget, original-lock and cross-ledger TOCTOU contract must precede any durable cancellation dispatcher. Bilingual report self-check covers outcomes, counts, risks, non-actions and next steps without real secrets.
