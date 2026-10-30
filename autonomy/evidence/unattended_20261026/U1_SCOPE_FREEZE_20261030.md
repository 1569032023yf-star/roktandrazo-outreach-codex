# U1功能范围冻结 / U1 functional scope freeze

依据：用户2026-10-30最新P0/P1排序。本文件冻结交付边界，不声明尚未完成的代码、审核或生产能力已经完成。 / Authority: the user's2026-10-30 P0/P1 priorities. This freezes delivery boundaries without declaring unfinished implementation, review or production capability complete.

## P0交付 / P0 delivery

1. 取消终态与持久恢复：沿用唯一Inventory的逻辑身份、原claim和独立费用预留；版本化终态必须关联原执行drained终态、原预算终态及独立费用回执。独立持久恢复日志记录准备与完成，真实退出/重开数据库验证中间故障不退款、不重放；不新增取消派发器。 / Cancellation terminal and durable recovery: preserve the sole Inventory identity, original claim and separate cost reservation. Join versioned terminal proof, drained original execution, original budget and independent cost receipts. A separate durable journal records preparation/completion; real exit/reopen tests must prove no refund or replay through intermediate failures. No cancellation dispatcher is added.

2. 默认禁用Windows宿主包：安装/依赖验证/回滚实现必须可执行，使用专属低权限身份，默认禁用且绝不自动启动；不创建Inventory或调度器。实际二进制与运行依赖缺失时拒绝生成可部署包，不能以JSON声明代替安装产物。回滚保留所有claim、UNKNOWN、预算、取消和恢复日志。 / Disabled Windows host package: executable installation/dependency verification/rollback tooling, dedicated low-privilege identity, disabled by default and never auto-started; no new Inventory or scheduler. Missing real binaries/dependencies must block deployable package generation. Preserve all claims, UNKNOWN outcomes, budgets and cancellation/recovery journals during rollback.

3. 固定完整候选：冻结源码/脚本及依赖清单，完成包导入闭包、相关组合测试和固定基线可比回归；独立Reviewer审核整个候选及回滚，不能继承旧局部PASS。原833项历史比较仅保留其固定版本口径。 / Complete pinned candidate: freeze source/scripts/dependencies; run package import closure, combined tests and comparable baseline regression. An independent reviewer must inspect the whole candidate and rollback rather than inherit scoped PASS verdicts. Earlier833-test comparisons remain version-scoped.

## P1接入及最终验收 / P1 integration and final acceptance

WorkBuddy通过既有GitHub通道验证真实执行身份、有效ACL、非交互代理出口、实际发布器对新增文件/依赖/原子替换/保留账本回滚的支持。批准来源不等于OS事实；交互7877和HKCU Run不等于无人登录。固定可审包完成后才提交一次性最小管理员授权，明确安装对象、路径、权限、禁用注册、维护窗口、启用/唯一权威切换及安全回滚范围。 / WorkBuddy validates actual execution identity, effective ACLs, noninteractive proxy egress and publisher support through the existing GitHub channel. Trusted provenance is not OS truth; interactive7877/HKCU Run is not login-free operation. Request one bounded administrator approval only after the reviewable package exists, identifying installation targets, paths, permissions, disabled registration, maintenance window, activation/sole-authority switch and safe rollback.

正式部署和验收仅通过现有受控入口及原Inventory自然运行，要求重启/注销/桌面关闭证据、互斥与故障恢复及两次真实自然运行。当前SAFE与增长缺少可比权威证据时仍UNKNOWN。 / Production deployment and acceptance use the existing controlled channel and original Inventory's natural runs, including reboot/logoff/desktop-closed evidence, exclusion/recovery and two actual scheduled cycles. Current SAFE/growth remain UNKNOWN without comparable authoritative evidence.

## 明确排除 / Explicit exclusions

不新增采集、邮件、配额、来源规避、通用命令/SQL入口、自动重放或新业务功能。SMTP关闭，不访问生产DB，不启动旧BDExecutionHost，不默认LocalSystem，不重复apply4A8U/V/W。 / No new collection, mail, quotas, source bypass, generic command/SQL access, replay or business features. SMTP stays disabled; no production DB access, old BDExecutionHost start, default LocalSystem or repeated4A8U/V/W application.

执行结果：范围已冻结，三项P0完成状态以固定候选最终审核报告为准。未执行：生产安装、身份/ACL修改、启用及采集。风险：真实依赖与权限证据未完备时，最终安装包/生产验收必须保持未完成。数量：3项P0、2项P1。下一步：并行完成取消恢复和安装工具，再串行集成/审核。敏感信息检查：无凭据、客户资料或代理地址。 / Result: scope frozen; completion of the three P0 items follows the final pinned-candidate review. Not performed: production installation, identity/ACL changes, activation or collection. Risk: missing dependency/permission evidence keeps package/production acceptance incomplete. Counts: three P0 and two P1 items. Next: parallel recovery/installation implementation, then serial integration/review. Sensitive-data check: no credentials, customer records or proxy addresses.
