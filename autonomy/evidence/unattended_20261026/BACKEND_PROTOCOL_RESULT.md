# 版本化离线执行合同集成 / Versioned offline execution contract integration

固定源码 / Source candidate: `d548552`。

新增backend v1精确版本准入与签名绑定，操作携带Inventory、claim、原锁、账本指纹、预算wall和幂等身份。未声明版本或不匹配时在claim前拒绝。旧无版本admission仍可处理已有UNKNOWN的签名对账，不能继续派发。 / Backend v1 admission binds the exact version on backend and signed evidence. Operations carry Inventory, claim, original lock, ledger fingerprints, reserved wall and idempotency identity. Missing/mismatched versions fail before claim. Historical unversioned admissions remain usable for authenticated UNKNOWN reconciliation, but cannot dispatch.

实际测试：作者22项定向通过；主线7模块组合87项通过（9.899秒）；固定Git字节清单更新后隔离导入2项通过（1.536秒）。独审以BACKEND_PROTOCOL_REVIEW.md为准，未返回时PENDING。未运行当前候选可比全量，NO_NEW_REGRESSION=UNKNOWN；不得继承旧833结论。 / Actual validation:22 author-targeted tests passed;87 tests across7 modules passed in9.899s;2 pinned-package import tests passed in1.536s. Independent verdict is in BACKEND_PROTOCOL_REVIEW.md and remains PENDING until returned. No comparable full-suite run covers this candidate; NO_NEW_REGRESSION=UNKNOWN, without inheriting earlier833-test results.

兼容风险：旧离线执行方必须重新签发v1 admission并实现相应backend合同；仅设置版本标签不能证明硬时限、持久幂等或外部进程排空。此次没有取消API、强制终止实现或正式后端。fake取消ack只是无效结果形状，timeout是异常注入。 / Compatibility: offline callers must issue v1 admissions and implement the backend contract. A version label does not prove hard deadlines, durable idempotency or external process draining. No cancellation API, forced termination or formal backend was added. Fake cancellation acknowledgement tests invalid result shape; timeout is injected failure.

包清单已按Git blob重算，生产目标仍UNAPPROVED。回滚仍遵守U1_RELEASE_GATES.md，保留当前账本/UNKNOWN/预算预留；不能以恢复旧数据库或忽略账本的旧执行器回滚。版本切回前必须排空并验证精确协议、锁与schema兼容。 / Source manifest uses recalculated Git-blob hashes; production targets remain UNAPPROVED. Rollback retains current ledgers, UNKNOWN and reservations under U1_RELEASE_GATES.md; stale database restoration or executors ignoring ledgers are forbidden. Any version rollback requires draining and exact protocol/lock/schema compatibility checks.

Issue2已核对最新仍6435605069，未重复请求。下一项为持久取消请求身份/去重及回执对账的离线实现，保持生产入口禁用。无生产数据库访问、Inventory创建、采集、SMTP、配额、账号/ACL/系统任务变更。 / Issue2 still ends at6435605069 without duplicate requests. Next: offline durable cancellation identity/deduplication and receipt reconciliation, keeping production disabled. No production database access, Inventory creation, collection, SMTP, quota, account/ACL or scheduled-task change occurred.

独立审核已返回PASS_FOR_OFFLINE_BACKEND_V1_CONTRACT，绑定d548552完整SHA，22项独立测试通过（6.446秒）；见BACKEND_PROTOCOL_REVIEW.md，覆盖上文PENDING条件。 / Independent review returned PASS_FOR_OFFLINE_BACKEND_V1_CONTRACT bound to the full d548552 SHA;22 independent tests passed in6.446s. See BACKEND_PROTOCOL_REVIEW.md, superseding the pending condition above.

SCOPED_REVIEW_PASSED=true; DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
