# 一次性管理员操作申请准备状态 / One-time administrator request readiness

REQUEST_STATUS=NOT_READY_NOT_REQUESTED

中文：本文件不是安装指令或当前批准请求。正式执行backend、受信OS证据生产端、批准非交互出口、runtime依赖指纹及发布器新增文件/账本保留回滚兼容仍缺，不能要求用户批准不可执行的包。保持现有唯一Inventory、禁用候选XML与生产派发关闭，不创建用户、任务或修改ACL。

English: This is neither an installation instruction nor a current approval request. Formal backend, trusted OS collectors, approved egress, runtime fingerprints and new-file/ledger-preserving rollback compatibility remain absent. An incomplete package must not be presented for approval. Preserve the original Inventory, disabled XML and denied production dispatch; create no account/task and change no ACL.

中文：条件齐备且独审通过后，申请应只包含精确低权限执行身份、该身份所需批处理登录权、固定运行时只读及DB/日志/缓存/审计目录最小写ACL、禁用态任务注册；批准出口健康探针仅对指定身份及批准目标。切换窗口先停旧派发、排空与核对UNKNOWN、保留账本、更新authority epoch，再验证唯一权威。回滚先禁用新执行器并排空，旧执行器须能读取当前ledger/schema/epoch及预算，否则保持关闭。不得使用LocalSystem、复活旧服务、扩大预算或启用SMTP。

English: Once evidence and independent review pass, request only the exact nonadmin identity, scoped batch logon, read-only runtime and minimum database/log/cache/audit write ACLs, and disabled task registration. Egress probes must bind the approved identity and targets. Stop old dispatch, drain and reconcile UNKNOWN, preserve ledgers, advance authority epoch and verify sole authority before cutover. Rollback disables/drains the new host first; the old executor must understand current ledger/schema/epoch/budgets or remain stopped. No LocalSystem, zombie service, budget increase or SMTP.

中文：验收需要维护窗口内授权操作、真实OS启动/登录审计及至少两个正常计划周期；未授权注销或重启。当前未执行管理员动作，数量0，下一步继续既有正式合同交接。自检双语、无秘密、未将未完成标记完成。

English: Acceptance requires authorized window operations, actual boot/logon auditing and at least two normal scheduled cycles. Logout/reboot is not authorized here. Administrator actions performed: zero. Next continue the existing formal contract handoff. Bilingual and sensitive-data self-check passed; incomplete work remains incomplete.
