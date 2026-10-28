# 取消意图账本独立审核 / Independent cancellation-intent journal review

结论 / Verdict: PASS_FOR_OFFLINE_CANCELLATION_INTENT_ONLY

范围 / Scope: `CancellationJournal`、`reserve_cancellation` 及四项新增测试；不包含取消执行器。 / CancellationJournal, reserve_cancellation and four new tests; no cancellation executor.
审核时 HEAD / HEAD at review: `7e4c3d51d5b757d8a4a614e4ffae0daf70602532`；结论绑定下面实际工作树字节，不假定 diff 已包含在 HEAD。 / Verdict binds to the working-tree bytes below, not an assumption that the diff is in HEAD.

## 实际验证 / Executed validation

`python -B -m unittest test_single_slot_adapter -q`: 26 tests passed, 4.711 seconds.

## 审核发现 / Findings

在可信本地路径、可信注入依赖的离线意图记录范围内，未发现阻断缺陷。 / No blocking defect found within offline intent recording with trusted local paths and injected dependencies.

- journal 使用 BEGIN IMMEDIATE 与 synchronous FULL，严格匹配 schema SQL 和 user_version；已有同身份同 binding 返回 DUPLICATE_RESERVED，冲突拒绝。提交前故障回滚，提交后确认丢失返回 UNKNOWN；重开后识别已提交记录。 / Journal uses BEGIN IMMEDIATE and synchronous FULL, with exact schema SQL/user_version checks. Same identity/binding returns DUPLICATE_RESERVED; conflicts are rejected. Pre-commit faults roll back; post-commit acknowledgement loss returns UNKNOWN and reopening recognizes the persisted record.
- 路径规范化并用 samefile 拒绝 protected 主数据库及锁文件的同路径、符号链接目标或硬链接别名。 / Resolved paths and samefile reject aliases of protected primary database/lock files, including hard links.
- adapter 校验签名、原 admission、当前锁/运行身份、journal路径身份、协议、原 claim、预算 request/run/slot/epoch/owner；只对未清 slot 与未清预算记录意图。 / Adapter checks signature, admission, current lock/runtime identity, journal path identity, protocol, original claim and budget request/run/slot/epoch/owner, recording only unresolved slot/budget intent.
- 所有 journal 正常返回的 allow_cancel_dispatch 与 production_execution 均为 False；没有 cancel_once、退款或清锁调用。相关测试确认未知 slot 与 reserved budget 不变、backend.calls 不增加。 / Every normal journal return keeps allow_cancel_dispatch and production_execution False. No cancel_once, refund or fence-clear call is added. Tests confirm unchanged unknown slot/reserved budget and no additional backend calls.

## 字节封签 / Reviewed hashes

Windows SHA256:
- `autonomy/single_slot_adapter.py`: `b39afe15eb37decbfb08febe91d93635e50c42b7e91d42dbc734e646c8263ba3`
- `test_single_slot_adapter.py`: `f203a8f850c0b12348355573a2cc6daafc1916b0c552d90960b7b47f818ed117`

## 重要边界 / Limits

journal.reserve 是可信内部持久化接口，不自行验签；安全绑定来自 adapter 调用。路径检查不是恶意文件系统竞争的隔离边界，也没有验证任意生产数据库路径或 SQLite sidecar 路径，部署仍需批准独立目录与 ACL。 / journal.reserve is a trusted internal persistence primitive, not a signature verifier; bindings are enforced by its adapter caller. Path checks do not isolate hostile filesystem races or validate arbitrary production/SQLite sidecar paths; approved dedicated directories and ACLs remain deployment requirements.

slot读取、budget读取与journal写入不是跨库原子操作，记录只表示观测到的取消意图，绝不能作为真实取消 dispatch 准入。重开测试仍在同进程持锁窗口；不证明进程崩溃、真实取消完成或外部副作用已清理。 / Slot reads, budget reads and journal writes are not cross-database atomic. Records represent observed cancellation intent only and must never authorize cancellation dispatch. Reopening tests remain in one process/lock window and do not prove process-crash recovery, actual cancellation or external-effect cleanup.

未操作生产数据库、网络或SMTP；未修改实现、清单、队列或提交。本结论不升级整体 U1、RELEASE_READY、生产部署或生产验收。 / No production database, network or SMTP operation occurred. Reviewer did not modify implementation, manifest or queue or create a commit. This verdict does not upgrade overall U1, RELEASE_READY, deployment or production acceptance.

最终固定源码 / Final pinned source: `650df4b`；固定后独立复核两个文件哈希与上述审核字节一致。 / Both file hashes were independently rechecked after pinning and match the reviewed bytes above.
