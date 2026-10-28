# 回滚计划准入独立审核 / Independent rollback-plan admission review

结论 / Verdict: PASS_FOR_OFFLINE_ROLLBACK_PLAN_ADMISSION

范围 / Scope: `autonomy/rollback_admission.py`, `test_rollback_admission.py`。
测试执行时 HEAD / HEAD at execution: `03bd972c5c25d5689fb8be1078606f13ec055550`。最终源码固定 / Final source pinned: `15b5267`；固定后复核下列哈希一致 / hashes below rechecked unchanged after pinning.

## 实际验证 / Executed validation

`python -B -m unittest test_rollback_admission -v`: 9 tests passed, 0.004 seconds.

审核版本已包含 claimed_slots/running_slots 必须为整数零的更新。 / Reviewed version includes the requirement that claimed_slots/running_slots must be integer zero.

## 结论依据 / Findings

未发现本次范围内阻断缺陷。 / No blocking defect found within scope.

- expected 字段集合固定，哈希格式与身份/锁格式受限，schema/epoch 拒绝 bool；授权 epoch 必须递增。证据绑定检查同时比较类型和值。 / Expected context has a fixed field set, bounded hash/identity/lock formats, strict integer schema/epochs and increasing authority epoch. Evidence binding compares both type and value.
- 使用既有 EvidenceConsumer 的可信来源、HMAC、身份、kind、时间及收据校验；篡改、过期、未来及错身份负例拒绝。 / Existing EvidenceConsumer enforces trusted source, HMAC, identity, kind, freshness and receipt checks; tampered, stale, future and mismatched identity cases are rejected.
- 全部前置事实必须严格 True，restore_old_database 必须严格 False；claimed/running/unknown slots 与 unknown/reserved/overrun budget 必须严格整数零。缺字段与非整数零均不准入。 / Required facts must be exactly True, restore_old_database exactly False, and all slot/budget counters exactly integer zero. Missing fields and noninteger zero values are rejected.
- 每个返回分支 allow_dispatch 均为 False，成功仅代表 PLAN_ONLY_ADMITTED；无文件、数据库、网络、调度或进程副作用。输出只含固定状态与原因，不回显证据或秘密。 / Every return keeps allow_dispatch False; success means PLAN_ONLY_ADMITTED only. No file, database, network, scheduling or process side effects occur. Outputs contain fixed statuses/reasons without echoing evidence or secrets.

## 字节封签 / Reviewed byte hashes

Windows 工作树 SHA256 / Windows working-tree SHA256:

- `autonomy/rollback_admission.py`: `dcf3ce8c4093ed903706089e83edce07bfcc657a697e67076d527a0095cceb91`
- `test_rollback_admission.py`: `61cdf2d5a4fc2f804ee9d2ec0d2c53021fb947d1b8d6da073460687493525faf`

## 边界 / Limits

调用方必须从可信当前状态提供 expected，并使用真实 EvidenceConsumer；不能从同一待验信封复制 expected。签名证明来源，不证明采集者陈述真实。返回值不是回滚执行授权、原子锁或 TOCTOU 防护。真实执行前仍需当前锁、停机排空、可信账本与权威切换验证。 / Callers must supply expected from trusted current state and use the real EvidenceConsumer, never copy expected from the envelope. A signature authenticates provenance rather than collector truth. The return is neither execution authorization nor an atomic lock or TOCTOU defense. Actual execution still requires current lock, drain, trusted ledger and authority-transition verification.

本审核未执行真实回滚、旧数据库恢复、生产发布、采集或邮件；不证明 U1、RELEASE_READY、PRODUCTION_DEPLOYED、PRODUCTION_ACCEPTED 或业务增长完成。 / No actual rollback, old database restore, production release, collection or email was performed. This review does not establish completion of U1, RELEASE_READY, PRODUCTION_DEPLOYED, PRODUCTION_ACCEPTED or business growth.

