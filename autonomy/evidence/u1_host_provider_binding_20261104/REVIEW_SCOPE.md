# 固定候选独立审核 / Fixed candidate independent review

Source:69eb1887800f046b6d860cbefad6bd99f3c35169
Independent Reviewer:PENDING; implementation checks are not independent approval.

中文：审核安装计划的Provider引用成对字段、绝对路径和单独批准摘要，安装器固定外部配置，bootstrap严格传递，宿主在读取快照/owner和监听之前验证并在整个生命周期持有原生文件/祖先句柄。确认密钥不写入runtime.json、环境或HTTP，不把引用当作派发授权。旧配置不带Provider字段仍兼容；Worker尚未接入，不能声称业务闭环。
English: Review paired Provider references, absolute paths and separately approved digests; installer pins, strict bootstrap forwarding, and native lifetime file/ancestor handles validated before snapshot/owner/listener access. Verify that runtime.json/environment/HTTP do not receive credentials and references grant no dispatch authority. Legacy configurations remain compatible; Worker wiring is incomplete and business closure is not claimed.

中文：审核Publisher对真实外置块日志的兼容修复。内容从固定AUDIT下原operation_id对应的files日志旁读取，复用HostFileTransaction的块目录身份和SHA核验；不接受任意块路径或未知内容，不重放。最大文件数与8192包文件+2生成配置对齐，旧内嵌日志仍使用同一decoder。需要复核前后回执和完整包数约束；维护锁在篡改时保持UNKNOWN。
English: Review Publisher support for actual blob-backed journals. Payloads are read beside the fixed AUDIT files journal for the original operation_id, using HostFileTransaction directory identity and digest validation, without arbitrary blob paths/replay. Capacity matches8192 package files plus2 generated configs; legacy inline journals use the same decoder. Recheck old/current ownership receipts and scope bounds; tampering must retain maintenance with UNKNOWN.

中文：42项定向组合通过，包括隔离真实文件首装/升级/两类回滚。SCM/ACL为隔离替身，不是真实Windows服务安装验收。真实费用回执CONTRACT_MISSING。所有最终状态和安全门禁保持false。
English:42 targeted combined checks pass, including real isolated file first-install/upgrade/both rollbacks. SCM/ACL are isolated substitutes, not actual Windows-service installation acceptance. Authoritative cost/receipt contracts remain CONTRACT_MISSING. All final states and safety gates remain false.
