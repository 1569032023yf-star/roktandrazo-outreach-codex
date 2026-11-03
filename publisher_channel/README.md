# 原发布器维护接线开发副本 / Original publisher maintenance development copy

中文：此目录是既有部署通道的离线开发副本。`executor.py` 的原 `inventory_acquire` 事务保留维护标记检查，另增加严格U1安装入口；`bridge.py` 复用原Bearer认证。来源见 `SOURCE_BINDING.json` 与 `CHANNEL_SOURCE_BINDING.json`；原维护差异见 `MAINTENANCE_ADMISSION.patch`，通道接线差异见 `CHANNEL_INTEGRATION.patch`。未修改现场文件、seal、白名单或路由；候选新增HTTP入口不等于已部署。不要直接运行现场配置或自动复制到现场。

English: This is an offline development copy of the original channel. The original executor admission retains its maintenance check and adds a strict U1 entry; the bridge reuses original Bearer authentication. Both source bindings and patches are retained. Site files, seals, target allowlists and HTTP routes remain unchanged; the candidate HTTP entry is not deployed. Never run site configuration or automatically copy this code to the site.

中文：`install_maintenance.py` 是 Publisher 受信调用方使用的内部会话实现，不是公开 API、调度器或安装授权。调用方须提供已授权数据库连接、受控安装适配器和独立最终核验器；它不发现生产数据库、不执行外部命令、不创建任意路径。维护 invocation ID 与目标安装 journal ID 分开：显式回滚使用新的维护 invocation，仍绑定旧目标、源码、清单和动作。

English: `install_maintenance.py` implements an internal session for a trusted publisher caller, not an API, scheduler or installation grant. The caller supplies an already-authorized connection, controlled installer adapter and independent final verifier. The module discovers no production DB and runs no commands or arbitrary paths. Maintenance invocation IDs differ from target install-journal IDs, allowing separately bound explicit rollback.

中文：取得维护权后，安装意图、返回、最终核验和释放都有持久记录。最终核验凭据与释放同一事务提交；异常不在 finally 中释放。突然退出或未知结果只能显式只读核对，不能再次调用安装器。PowerShell 内部协调器在写入阶段及文件 helper 前后核验绑定维护会话；公开 Execute hard gate 保留。

English: Acquisition atomically persists the marker, replay tombstone and full session context. It is followed by durable installation-intent, return, verification and release records. Final proof and release commit atomically. Exceptions never finally-release. The internal PowerShell coordinator checks the bound session across mutation phases and file-helper calls; public Execute remains hard rejected.

中文：未知状态可显式只读核对；部分应用则在受信适配器确认旧进程已结束后，使用新 recovery_id 在同一维护权下交接为 recover 子会话，不重新运行正向安装。子会话也可在中断后重开记录并继续显式补偿。父会话交接后在数据库事务内被永久禁止再次推进或释放；迟到的状态写入和核验回执不能覆盖交接。

English: Unknown state permits explicit read-only reconciliation. Partial application requires the trusted adapter to confirm the previous process has stopped, then uses a new recovery ID to hand off compensation under the same exclusion. Interrupted compensation can reopen its recorded child and explicitly compensate again. Handed-off parents are permanently barred from advancing or releasing within the database transaction; late state writes and verifier replies cannot override handoff.

中文：`POST /v1/u1-install` 先使用原通道Bearer认证，再由原executor调用 `install_admission.py`。请求只含release ID、维护invocation ID、动作和必要的目标/恢复ID；不能提交批准记录、路径、摘要或命令。动作包括install、upgrade、rollback、status、reconcile及compensate。独立批准记录只能来自原配置内受seal覆盖的 `u1_install`；固定配置、scope、seal句柄持续到最终核验。无seal、seal篡改、内存/磁盘配置不符、非唯一Inventory、原锁前缀不符或安装/全链审核门禁关闭时拒绝。不存在的正式数据库不创建。

English: POST /v1/u1-install first uses the original Bearer check, then the original executor calls install_admission.py. Requests contain only release ID, invocation ID, action and necessary target/recovery IDs, never approval records, paths, hashes or commands. Actions are install, upgrade, rollback, status, reconcile and compensate. Independent approvals originate only from seal-covered u1_install configuration; configuration, scope and seal handles remain pinned through verification. Missing/tampered seals, loaded/disk mismatch, wrong Inventory/lock prefix and closed install/full-review gates refuse. Missing official databases are never created.

中文：重复执行请求只返回已有持久记录；UNKNOWN不重放。status使用只读数据库连接，不改在途标记，也不声称当前现场终态已验证。reconcile先核验旧进程结束，再独立检查终态；compensate使用新recovery ID交接同一维护权。维护意图先于进程；核验及释放仍原子提交。原seal是既有一致性机制，不是加密签名，依赖原通道配置的受信本地所有权；不能把HTTP调用或测试fixture当作安装授权。

English: Repeated execution requests return durable records only; UNKNOWN never replays. Status uses a read-only DB connection without changing in-flight markers or claiming fresh site verification. Reconcile verifies the old process ended before independent terminal checks; compensate hands off the same exclusion using a new recovery ID. Intent precedes launch and verified release remains atomic. The original seal is a consistency mechanism, not a cryptographic signature, and retains the channel's trusted local-configuration ownership boundary. HTTP access/test fixtures are not installation authorization.

中文：安装器和独立终态核验器已在候选代码接线，但固定Windows PowerShell实际成功命令、真实SCM/ACL、正式backend和完整发布交付仍待验收。当前正向入口测试使用明确的隔离安装/进程/终态回调替身；不能替代全链Windows实测。完整审核和授权前 `allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false`。此目录不启动服务器、服务或Inventory。

English: Candidate code connects the installer and independent terminal verifier, but successful fixed Windows PowerShell execution, actual SCM/ACL, formal backend and complete release delivery still require acceptance. Positive entry tests explicitly use isolated installation/process/terminal callback doubles and do not substitute for full Windows integration. Keep all installation, dispatch, cancellation and SMTP gates false before complete review and authorization. This directory starts no server, service or Inventory by itself.
