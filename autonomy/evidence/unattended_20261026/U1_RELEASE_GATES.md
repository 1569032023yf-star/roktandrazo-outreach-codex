# U1集成发布门禁 / U1 integration release gates

取消费用增量：回滚必须同时保留原执行预留、独立取消费用预留及CancellationJournal；不可仅回滚journal或源码就退款。旧意图无费用合同不视为新版准入，换锁/过期请求不自动续约；新候选独审待完成，allow_cancel_dispatch=false。 / Cancellation-cost increment: rollback must preserve original and separate cancellation reservations plus CancellationJournal. Journal/source rollback never refunds costs. Legacy intents are not new cost admission; changed locks/expired signatures do not renew automatically. New independent review is pending and cancellation dispatch stays false.

取消意图日志增量：任何回滚必须保留当前CancellationJournal及其RESERVED_RECONCILE_ONLY记录；禁止删除/还原旧日志来重新消费取消意图。该日志不授予取消派发能力；旧执行器忽略它不能作为恢复派发的理由。独立schema version1仅在隔离开发中验证，生产目标及初始化尚未批准。 / Cancellation-journal increment: rollback must preserve current CancellationJournal and RESERVED_RECONCILE_ONLY records. Never delete or restore an older journal to consume an intent again. It grants no cancellation-dispatch capability; an old executor ignoring it cannot justify resumed dispatch. Separate schema version1 is verified only in isolated development; production targets/initialization remain unapproved.

基线 / Baseline: b3a0d3ae26ef99fea5f458ec029301d233a27f7c，已核对远端，比用户所列18ef758多一项临时账本实验提交。用户指令现在要求实际持久协议，旧实验审核不能继承为U1整体审核。

The verified remote baseline adds the temporary-ledger experiment to the user's18ef758 reference. U1 requires a durable protocol; prior experiment reviews cannot establish overall U1 approval.

## 生产边界 / Production boundary

新增模块当前仅开发集成候选，正式发布器新增文件/备份/删除回滚支持尚未证明。禁止直接复制新文件到生产。需要确认实际目标文件SHA、执行入口范围、schema迁移兼容、旧版本遇新schema的行为、备份可恢复与唯一Inventory锁衔接。

New modules remain development integration candidates. Formal deployer support for new files, backup and removal rollback is unproven; direct copying to production is forbidden. Verify exact target hashes, entrypoint scope, schema compatibility, old-version handling of new schema, restorable backup and the sole Inventory lock integration.

回滚不得恢复旧数据库快照而抹除已经发生的claim、UNKNOWN、预算预留或首次资格记录。先禁用新派发并排空，UNKNOWN先正式对账；保留账本，旧权威只能在更新epoch、互斥及兼容验证后恢复。若旧执行器不会读取新ledger，不能以恢复旧程序作为安全回滚结论，必须保持派发关闭至适配完成。

Rollback must never erase committed claims, unknown outcomes, reservations or qualification history by restoring a stale database snapshot. Disable dispatch and drain first; reconcile unknown effects through the formal channel. Preserve the ledger. Resume the previous authority only with a new epoch, exclusion and verified compatibility. An old executor that ignores the ledger is not a safe rollback target; dispatch stays disabled until adapted.

## 尚未发出的管理员申请 / Administrator request not yet issued

目前无需用户批准不完整方案。完成独审与受控包后，单次最小申请才包含专用非管理员身份、限定批处理登录权、精确目录ACL、禁用态任务注册、获准非交互出口、受控窗口内排空切换及回滚验收。不得包含默认LocalSystem、恢复旧僵尸服务、扩大采集配额、发信或第二Inventory。

No approval is requested for an incomplete package. After independent review, the minimum request may cover a dedicated nonadmin identity, scoped batch logon, exact directory ACLs, disabled task registration, approved noninteractive egress, drained cutover and rollback validation within an approved window. It excludes LocalSystem defaults, legacy zombie service revival, quota increases, email and a second Inventory.

## Provider独立门禁 / Separate Provider gate

Issue2最新仍为6402130583消费回执，缺scraper批准生产SHA/字节及封签范围、精确Service兼容；8d63d2d及30fccc9既有审核范围保留，不重做基础诊断。鉴权历史故障已恢复，不再列为持续阻塞。没有新生产周期证据，当前SAFE、增长、无人登录周期均UNKNOWN。

Issue2 still ends at acknowledgement6402130583. Approved scraper bytes/hash/scope and exact Service compatibility remain missing. Preserve existing8d63d2d/30fccc9 review scope without rebuilding diagnostics. Historical authentication recovered and is not a continuing blocker. Current SAFE, growth and login-free cycles remain UNKNOWN without new live evidence.
