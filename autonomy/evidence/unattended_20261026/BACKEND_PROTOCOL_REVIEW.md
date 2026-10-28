# Backend v1 协议独立审核 / Independent backend v1 protocol review

结论 / Verdict: PASS_FOR_OFFLINE_BACKEND_V1_CONTRACT

范围 / Scope: 当前 `autonomy/single_slot_adapter.py` 与 `test_single_slot_adapter.py` 协议 diff；结论绑定以下工作树字节。 / Protocol diff in the adapter and tests; verdict binds to working-tree bytes below.

## 实际验证 / Executed validation

`python -B -m unittest test_single_slot_adapter -q`: 22 tests passed, 6.446 seconds.

## 审核发现 / Findings

本范围未发现阻断缺陷。 / No blocking defect found within scope.

- execute 的 backend.protocol_version 与签名 admission.backend_protocol 均须严格为 v1 字符串，错误或缺失版本在 claim 前拒绝；不新增生产范围准入。 / Both backend.protocol_version and signed admission.backend_protocol must strictly match the v1 string; wrong or missing versions are rejected before claim, without adding production admission.
- operation 包含 schema、协议版本、Inventory、slot/epoch/owner、run/request、claim token、原锁身份与账本身份、backend身份及实际预留 wall bound；idempotency_key 对完整 operation 摘要，未包含摘要自身。 / Operation includes schema, protocol, Inventory, slot/epoch/owner, run/request, claim token, original lock and ledger identities, backend identity and reserved wall bound. idempotency_key hashes the full operation excluding itself.
- reconcile 继续要求原签名、身份、锁、claim 及预算绑定；省略新协议字段的 legacy admission 不可 execute，但可显式对账。该兼容不增加 backend 调用。 / Reconciliation retains signature, identity, lock, claim and budget checks. Legacy admissions lacking the new field cannot execute but can explicitly reconcile without a backend call.
- 假 cancel_ack 不符合双回执合同；TimeoutError 和该假确认均使 slot UNKNOWN、预算 reserved，再次 execute 不重放。只有已验证终态回执进入结算清理。 / A fake cancel_ack fails the two-receipt contract; both it and TimeoutError preserve UNKNOWN slots and reserved budget, with no replay on another execute. Verified terminal receipts are required for settlement/cleanup.

## 字节封签 / Byte hashes

Windows 文件 SHA256 / Windows file SHA256:
- `autonomy/single_slot_adapter.py`: `f4ea4d5b0759cae85704f5c89799b9690baf865e4ef7aef317ccafbc853a3f28`
- `test_single_slot_adapter.py`: `517a955155617adfa8c871a420b82eeab67ff1ac34e7ad6e12f8e7640e87c8d2`

## 边界 / Limits

v1 标识是合同声明，不是后端真实持久幂等、deadline 强制或取消能力证明。idempotency key 绑定原锁/claim，不能单独作为换锁后跨运行重放安全证明；当前持久账本继续禁止不明结果重放。 / The v1 identifier is a contract declaration, not proof of durable backend deduplication, deadline enforcement or cancellation. The key binds the original lock/claim and alone does not prove replay safety across lock transitions; durable ledgers continue to block replay of unknown outcomes.

注入 backend 是可信代码依赖；operation 包含执行所需 claim token，仅传给该依赖，不应写入外部日志。新增测试使用 synthetic backend、临时数据库和 fixture 签名，没有真实取消 API、硬终止、进程树排空或生产验收。 / The injected backend is trusted code. Operation carries the execution claim token only to that dependency and should not be logged externally. Tests use synthetic backend, temporary databases and fixture signatures, not actual cancellation APIs, hard termination, process-tree drain or production acceptance.

未修改实现、共享清单或队列，未创建提交；本审核不升级 U1 整体、发布、部署或业务增长状态。 / Reviewer did not modify implementation, shared manifest or queue and created no commit. This review does not upgrade overall U1, release, deployment or business-growth status.

最终固定提交 / Final pinned commit: `d548552`。提交后两文件 SHA256 已独立复核，与上述审核字节一致。 / Both file hashes were independently rechecked after pinning and match the reviewed bytes above.
