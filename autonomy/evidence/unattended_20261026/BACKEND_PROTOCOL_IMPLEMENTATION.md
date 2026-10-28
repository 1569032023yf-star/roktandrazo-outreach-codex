# Backend v1 离线执行协议 / Backend v1 offline execution protocol

## 实现与结果 / Implementation and result
single_slot_adapter 新增精确字符串协议 rokt.offline-backend.v1：backend.protocol_version 与签名 admission.backend_protocol 均须匹配，缺失/错误类型/版本在 claim 前拒绝。旧离线签名 admission 未含该字段时执行拒绝，这是有意的 fail-closed 兼容变更；仅对账入口保留已有合同，以免阻断旧未知结果对账。没有生产路径受此变更启用。
Execution requires the exact backend protocol string on both backend and signed admission, rejecting missing or mistyped versions before claims. Existing signed offline admissions without this field intentionally fail closed for execution. Reconciliation retains its existing contract so historical unknown outcomes remain reconcilable. No production path is enabled.

execute_once(operation, deadline_monotonic=...) 的 operation 带版本化 schema、inventory_id、isolated_offline scope、production_execution=false、预算 wall 上限及幂等哈希。哈希绑定 slot/epoch/owner/run/request、claim token、具体账本与 runtime、backend、原锁实例；deadline 为同进程 monotonic 开始值加预算时间。backend v1 合同要求独立隔离执行及持久幂等，并在该时限内结束外部进程树；协议标签不能证明实现满足这些义务，也不是生产批准。
The versioned operation carries Inventory identity, isolated scope, explicit nonproduction execution, reserved wall limit and an idempotency digest binding claim, request, ledgers, runtime, backend and original lock. The monotonic deadline is local to the caller process. A backend implementation must durably deduplicate and enforce bounded external process-tree execution; a version label is neither capability proof nor production approval.

## 取消及硬时限边界 / Cancellation and hard-deadline boundary
没有新增取消入口或调用取消 API。将来取消必须有独立版本、同一 operation/claim/预算/锁绑定、持久取消请求去重；ack 只能表示请求收到，不可清锁、退款或重放。当前 fake cancel_ack 仅测试不合格结果形状；fake timeout 为确定性异常注入，不是实际进程终止测试。Python callback 不能由本适配器硬终止，晚返回拒绝与 UNKNOWN 保留是当前本地保障。
No cancellation API or invocation is implemented. Future cancellation requires a versioned, durably deduplicated request bound to the original operation, claim, budget and lock. An acknowledgement must never release locks, refund or replay. Fake cancel_ack tests invalid result shape only, and timeout injection does not prove process termination. The adapter cannot forcibly terminate Python callbacks; it rejects late results and preserves UNKNOWN.

## 验证 / Validation
python -B -m unittest test_single_slot_adapter -q：22 项通过，新增 4 项（含参数化子场景），覆盖版本拒绝、操作身份/时间预算、fake ack/timeout 后未知状态和预留保留及不重放。终态仍通过已有独立签名回执对账后才解除 fence。
22 tests passed, including four new tests with subcases for protocol rejection, operation identity/time binding and UNKNOWN/reservation/no-replay after fake acknowledgement or timeout. Only existing authenticated terminal reconciliation can close the fence.

## 状态、风险、下一步及自检 / Status, risks, next step and self-check
本范围开发和测试完成；独审待父任务执行。未提交、未改共享清单/队列、未网络或生产采集、未写生产数据库、未发信。完整生产 backend、真实硬超时/取消隔离及权限仍未完成。下一步独审精确源码，由主控固定 SHA 和清单。报告双语，结果/数量/未执行/风险/下一步齐全；仅测试虚构数据，无真实凭据。
Scoped implementation/tests complete; independent review remains for parent. No commit, shared manifest/queue edit, network/production collection, production database write or mail occurred. Production backend, actual deadline/cancellation isolation and permissions remain incomplete. Next: independent review and parent-owned pinned source manifest. Bilingual report self-check covers results, counts, non-actions, risks and next steps with synthetic fixtures only.

兼容补测 / Compatibility regression: 真正删除 backend_protocol 后重新签名的旧 admission 拒绝 execute，但仍可对先前 UNKNOWN 进行签名终态 reconcile；调用次数保持一次。 A re-signed legacy admission with the protocol field actually removed rejects execution while allowing signed reconciliation of a prior UNKNOWN, without another backend call.
