# 有界网络恢复与任务依赖重评 / Bounded network recovery and dependency dispatch

本板块只增加开发总控的纯策略和既有队列适配器，不增加自动化、Inventory、网络客户端或生产写入权限。代码不执行 shell、网络请求、睡眠或客户应用导入。实际请求仍由已批准的固定接口客户端执行，真实生产副作用仍走现有发布门禁。

This block adds pure engineering-control policies and an adapter for the existing queue. It creates no automation, Inventory, network client or production permission. The code executes no shell, request, sleep or customer-application import. Actual requests remain with the approved fixed-endpoint client; production mutations retain their release gates.

## 调用约定 / Invocation contract

真实 heartbeat 在解析、核验固定交接或正式接口回执后，通过 Python 模块注入调用以下接口；没有新的 CLI 启动器。`verified=True` 是调用方已经完成来源、schema、时间窗和SHA核验的契约，不是模块自行证明外部数据可信。事件只包含固定类型、证据SHA、观测时间及所满足依赖；禁止传入客户数据或原始异常文本。

After validating fixed handoff or official receipts, the genuine heartbeat calls the interfaces below by module injection. No new CLI launcher is added. `verified=True` attests the caller's completed source/schema/window/SHA checks; this module does not independently authenticate external data. Events contain only a closed type, evidence hash, observation time and satisfied dependencies. Never pass customer data or raw exception text.

```python
from datetime import datetime, timezone
from autonomy.task_dispatch import reconcile_queue

# root is the existing authorized development checkout.
# validated_events must be derived from independently verified receipts.
receipt = reconcile_queue(root, events=validated_events,
                          now=datetime.now(timezone.utc))
```

唯一权威队列仍是 `autonomy/runtime/queue.json`。适配器使用现有 `exclusive` 实例锁和 `atomic_json`，只改变满足依赖的开发任务状态，不领取或运行任务。新的任务ID必须经工程总控注册到既有执行能力后才能执行；`queued` 不代表可以绕过审核执行候选启动器。用于展示的 `AUTONOMOUS_TASK_QUEUE.json` 不可成为第二个调度器。

The sole authoritative queue remains `autonomy/runtime/queue.json`. The adapter uses the existing instance lock and atomic writer, changing only dependency-satisfied engineering task states. It neither claims nor executes tasks. New task IDs require registration with the existing engineering executor before running; `queued` never bypasses candidate-launcher review. Any `AUTONOMOUS_TASK_QUEUE.json` display projection must not become another scheduler.

## 网络预算 / Network budgets

`classify_failure` 只保留闭集错误代码。`recovery_plan` 返回计划而不执行：只读请求默认最多4次、15秒指数退避、最大基础退避900秒，并附加非负抖动。429的秒数或HTTP日期Retry-After为下限，不因上限或抖动被缩短；超过一年或非法值拒绝。预算用尽后持久化延期，不能仅因到点而重置。新的、已验证依赖变化可以授予新预算；同一个缓存SHA及逆序事件不能重复授予。

`classify_failure` retains closed error codes only. `recovery_plan` returns a plan, never execution: read-only requests default to four attempts, 15-second exponential delay, capped 900-second base delay, plus nonnegative jitter. Numeric or HTTP-date Retry-After is a lower bound and is never shortened by caps or jitter; invalid or greater-than-one-year values fail closed. Exhaustion is durably deferred and cannot reset solely because time passed. A new verified dependency change can grant a budget; the same cached hash or out-of-order event cannot repeatedly grant one.

认证失败不自动重试，只有新的已验证认证更新才重评。来源政策禁止不会由网络恢复或认证更新自动清除；应创建符合正式政策和授权的新任务。冲突需独立确认解决事件。未知错误保持阻塞。

Authentication failures do not retry automatically; only a new verified authorization update permits reassessment. Source-policy blocks are never cleared by network recovery or an authorization update; a separate supported and authorized task is required. Conflicts need a verified resolution event. Unknown errors remain blocked.

`register/apply/rollback/github-push` 永不自动重放；不确定结果一律先正式status、审计或远端HEAD对账。未知副作用标志、未核对的中断lease和旧UNKNOWN_OUTCOME不能被依赖事件解锁。Git只在实际观测远端SHA等于目标提交时返回push_success；远端为祖先只允许计划普通快进push，其后仍需读远端SHA。无force路径。

`register/apply/rollback/github-push` are never automatically replayed; uncertain outcomes require official status/audit or remote-HEAD reconciliation first. Unknown-effect flags, unreconciled interrupted leases and legacy UNKNOWN_OUTCOME cannot be unlocked by dependency events. Git reports push_success only when the observed remote SHA equals the target. An ancestor permits planning an ordinary fast-forward push, followed by remote verification. No force path exists.

## 断点与验收 / Checkpoints and acceptance

`checkpoint` 填齐任务ID、父目标、分支、工作树、输入/当前提交、最后核验步骤、测试/审核回执、release/op、已知副作用、下一动作、延期时刻、阻塞原因与完成证据字段。缺失证据用None，不伪造成功。保留现有计数语义：单元测试或手动模块调用不是两个真实无人值守工程周期，完整自主运行仍未验收。

`checkpoint` supplies task/parent/branch/worktree/input/current-commit/last-step/test/review/release/op/known-effects/next-action/retry-time/blocker/completion-evidence fields. Missing evidence stays None, never invented success. Unit tests and manually injected calls are not two genuine unattended engineering cycles; full autonomy remains unaccepted.

定向测试覆盖错误分类、Retry-After、预算保持、未知副作用、Git证据、依赖事件、防缓存重复、真实本地队列持久化及写入失败不覆盖原队列。没有生产、联网、SMTP或全量测试。独立审核和下一真实heartbeat调用仍需分别留存真实回执。

Focused tests cover classification, Retry-After, budget preservation, unknown effects, Git evidence, dependency events, cached-event replay prevention, real local queue persistence, and original-queue preservation on write failure. No production, network, SMTP or full-suite execution. Independent review and a future genuine heartbeat invocation each require separate actual receipts.
