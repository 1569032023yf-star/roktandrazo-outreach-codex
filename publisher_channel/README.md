# 原发布器维护接线开发副本 / Original publisher maintenance development copy

中文：`executor.py` 是既有部署通道执行器的只读来源副本，仅增加原 `inventory_acquire` 事务内的维护标记检查。来源及精确原始 SHA256 见 `SOURCE_BINDING.json`，最小差异见 `MAINTENANCE_ADMISSION.patch`。没有修改现场文件、注册 seal、允许的文件范围或 HTTP 路由。不要直接运行这个副本，也不要将它自动复制到现场。

English: `executor.py` is a development copy of the existing deployment executor, adding only the shared maintenance-marker check inside its original admission transaction. Source binding and the minimal patch are retained. Site files, seals, target allowlists and HTTP routes are unchanged. Do not directly execute this copy or automatically copy it to the site.

中文：`install_maintenance.py` 是 Publisher 受信调用方使用的内部会话实现，不是公开 API、调度器或安装授权。调用方须提供已授权数据库连接、受控安装适配器和独立最终核验器；它不发现生产数据库、不执行外部命令、不创建任意路径。维护 invocation ID 与目标安装 journal ID 分开：显式回滚使用新的维护 invocation，仍绑定旧目标、源码、清单和动作。

English: `install_maintenance.py` implements an internal session for a trusted publisher caller, not an API, scheduler or installation grant. The caller supplies an already-authorized connection, controlled installer adapter and independent final verifier. The module discovers no production DB and runs no commands or arbitrary paths. Maintenance invocation IDs differ from target install-journal IDs, allowing separately bound explicit rollback.

中文：取得维护权后，安装意图、返回、最终核验和释放都有持久记录。最终核验凭据与释放同一事务提交；异常不在 finally 中释放。突然退出或未知结果只能显式只读核对，不能再次调用安装器。PowerShell 内部协调器在写入阶段及文件 helper 前后核验绑定维护会话；公开 Execute hard gate 保留。

English: Acquisition is followed by durable installation-intent, return, verification and release records. Final proof and release commit atomically. Exceptions never finally-release. Crash/unknown recovery reconciles read-only without relaunching installation. The internal PowerShell coordinator checks the bound session across mutation phases and file-helper calls; public Execute remains hard rejected.

中文：尚未完成原通道支持入口到受控安装进程的适配器、独立目标/SCM/ACL 最终核验器及部署 seal 集成。当前回调测试不是这些工程的替代物。完整接线、独审和授权前 `allow_install=false; allow_dispatch=false; SMTP=false`，不得开始 WorkBuddy Windows 实际无人值守或生产验收。

English: The supported channel-to-installer process adapter, independent target/SCM/ACL final verifier and deployment-seal integration remain incomplete. Callback tests do not substitute for them. Keep installation, dispatch and SMTP disabled until integration, review and authorization are complete; do not enter actual Windows unattended or production acceptance yet.
