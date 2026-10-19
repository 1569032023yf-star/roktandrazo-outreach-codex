# V6 发布提案 / V6 release proposal

中文：未登记、未部署、不可执行发布。manifest 绑定本次只读取得的生产源码快照；在隔离临时目录中验证正向应用、after-SHA 和反向恢复字节。演练使用单次 Git 参数 core.autocrlf=false 保持生产 LF 字节，不修改全局 Git 配置。回归未全部通过，完整发布尚不可验收。

English: Unregistered, undeployed, non-executable release proposal. The manifest binds the approved read-only production source snapshot. Forward application, after-SHAs and byte-exact reverse restoration were rehearsed in an isolated temporary directory. One-command core.autocrlf=false preserves production LF bytes without changing global Git configuration. Regressions are not all passing; the complete release is not ready.

中文：5 个现有文件精确补丁、4 个新模块及单独哈希的原始 PNG；不含完整 preflight 源文件、凭据、数据库、业务策略、自动化配置、orchestrator 或 4B.1G。内部 QA 单独登记 3 个新增模块和原图，不改变客户发送器；通过现有腾讯企业邮箱 SMTP 向内部白名单试发，Gmail 仅收件。受控入口要求见 [接入要求](../../../docs/PHASE5A_CONTROLLED_OPERATIONS_REQUIREMENTS.md)。

English: Exact patches for five existing files, four new modules and a separately hashed original PNG. No complete preflight source, credentials, databases, operational policy, automation configuration, orchestrator, or 4B.1G is included. Internal QA separately registers three new modules and the original image without changing the customer sender, using existing Tencent enterprise SMTP for the internal allowlist. Gmail is the recipient only. See the [operations requirements](../../../docs/PHASE5A_CONTROLLED_OPERATIONS_REQUIREMENTS.md).

中文：离线可逆不等于生产备份/互斥/崩溃恢复通过。正式执行器必须重新核实所有哈希、备份和锁，审批新的 release。现有四操作和旧 SAFE50 release 均不可直接使用。任何未知新文件必须先检查不存在；回滚保留客户及发送审计。

English: Offline reversibility does not prove production backup, exclusion or crash recovery. The registered executor must recheck all hashes, backups and locks for a new release. Neither the current four operations nor the old SAFE50 release can directly execute this proposal. Require absence of new files before creation; preserve customer/send audits on rollback.
