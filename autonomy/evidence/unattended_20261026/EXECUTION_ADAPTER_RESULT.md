# 离线执行组合结果 / Offline execution composition

固定源码e3f3220318be0ae8d9368229aac432438913c5f4，独立审核见ADAPTER_REVIEW.md。新增单槽适配器组合签名准入、指定runtime与账本路径、实际进程实例锁、预算预留、claim/start、一次注入后端调用、双回执对账和预算结算。

Pinned source e3f3220318be0ae8d9368229aac432438913c5f4; see ADAPTER_REVIEW.md. The adapter composes signed admission, designated runtime and ledger paths, process-instance locking, reservation, claim/start, one injected backend call, authenticated receipts and budget settlement.

默认配置拒绝执行；仅接受isolated_offline范围。异常、迟到结果、丢失回执均不重放。旧已完成回执不能清除新UNKNOWN任务的树状态。计划中的签名缺槽完整保留，未知预算不自动退回。

Default configuration denies execution and only accepts isolated_offline scope. Exceptions, late results and missing receipts never authorize replay. Old completed receipts cannot clear a newer UNKNOWN execution tree. Signed missed slots are preserved; uncertain reservations are not automatically refunded.

验证：独立13项适配器测试通过；主线最终63项组合测试通过（4.907秒），包含多进程claim、进程退出注入、预算并发、签名适配、Windows禁用模板及回归日志测试。此前全量833项比较只覆盖b69214d，未冒充新适配器的全量结果。

Validation:13 independently run adapter tests passed; the final63-test combined run passed in4.907 seconds, including multiprocessing, exit injection, concurrent budgets, signed mapping, disabled Windows template and regression journaling. The earlier833-test comparison covers b69214d only, not the new adapter.

限制：同步Python回调不能在此被强制中断；后端仍须实现真实有界执行，当前只保证一次调用与迟到结果拒绝。签名模拟证据不证明真实Windows状态；没有正式执行后端、生产信任根或获准唯一锁接入。没有安装任务或改变生产入口。

Limits: a synchronous Python callback cannot be forcibly interrupted here. The backend must supply actual bounded execution; local guarantees are one call and late-result rejection. Synthetic signed evidence does not prove Windows state. Formal backend, production trust roots and approved sole-lock integration are absent. No task installation or production entrypoint change occurred.

DEVELOPMENT_COMPLETE=false; SCOPED_ADAPTER_REVIEW_PASSED=true; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.

下一步补跨登录/无人登录证据聚合，以及只读导入与迁移兼容准备；最终受控包具备后再列一次性最小管理员授权。无生产数据库写入、采集、发信或配额变更。报告自检：中英双语、范围与限制明确、无秘密和客户资料。

Next: implement cross-logon/login-free evidence aggregation and read-only import/migration preparation, then prepare a reviewable minimum administrator request. No production DB writes, collection, mail or quota changes. Report self-check: bilingual, explicit scope/limits, no secrets or customer data.
