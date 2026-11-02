# 禁用宿主候选操作合同 / Disabled host candidate contract

本文件描述离线开发候选；不是生产安装授权。继续采用已接受的非对称 ACL，不启动服务、不派发、不取消派发、不发送 SMTP。

This document describes an offline development candidate, not production installation authority. Preserve the accepted asymmetric ACL. Never start services, dispatch/cancel work or send SMTP.

## 安装与恢复 / Installation and recovery

使用固定包中的 `host/Install-DisabledHost.ps1`，独立批准并传入 `PackageRoot`、`ApprovedManifestSha256`、`RuntimePlan` 和 `ApprovedRuntimePlanSha256`。没有 `Execute` 只生成计划。首次安装要求代码、状态和服务均不存在。生产调用方必须通过正式发布通道持有唯一 Inventory 的维护排斥租约；目前脚本尚未强制验证该正式租约，因此候选不具备 RELEASE_READY 条件。

Use the fixed package's `host/Install-DisabledHost.ps1`, with independently approved package and runtime-plan hashes. Without `Execute`, it is plan-only. First installation requires absent code, state and service. The production caller must hold the sole Inventory's maintenance/exclusion lease through the formal publisher. This script does not yet enforce that formal lease, so the candidate is not RELEASE_READY.

升级增加 `Upgrade` 和 `ApprovedPreviousReceiptSha256`。旧凭据必须为 v2，精确列出所有受管文件和哈希。未受管文件不能被采纳或覆盖；只删除旧凭据列出而新包不再包含的文件。v1 凭据不自动迁移。服务必须保持相同账户、映像、Disabled 和 Stopped。

For upgrades, add `Upgrade` and the independently approved previous receipt hash. A v2 receipt must enumerate exact owned files/hashes. Never adopt or overwrite unmanaged files; delete only previously owned files removed by the new package. There is no automatic v1 migration. Require the same account/image and Disabled/Stopped service.

对已完成操作显式使用 `Rollback`；对中断操作使用 `RecoverInstall`。仍传入该操作的精确包和运行计划。两者先检查所有文件状态，再补偿 ACL、注册和文件。升级保留原有状态；首次安装回滚只按已记录身份逐级删除事务创建的空目录，将代码/状态新根恢复 ABSENT，未知内容保留并停止。文件原先不存在则恢复 ABSENT。任何未知文件、残缺日志或暂存残留均 STOP_AND_PRESERVE；不重放正向操作。不同操作的未决安装日志会封锁其他安装/回滚。旧的 `Rollback-DisabledHost.ps1` 只撤销服务注册，不能作为完整回滚入口。

Use explicit `Rollback` for a completed operation and `RecoverInstall` for an interrupted one, with that operation's exact package/plan. Both inspect all file states before compensating ACL, registration and files. Upgrades preserve existing state. Fresh-install compensation removes only recorded, identity-matching empty directories and restores new code/state roots to ABSENT. Unknown contents stop and preserve. Restore previously absent files to ABSENT. Unknown files, torn journals or unexpected staging artifacts stop and preserve; never replay forward effects. Other pending install journals fence all operations. The legacy rollback script unregisters only and is not the complete rollback entry point.

管理员审计目录必须预先由可信发布通道配置；脚本不会创建或自动修复其信任 ACL。保留所有 install/files/acl/state-create 日志；不把它们当作数据库备份。文件模块当前限制新内容及旧备份分别 16MiB，超限在修改前拒绝。

The administrator audit root must be provisioned by a trusted publisher; the script never creates/repairs its trust ACL. Retain all install/files/acl/state-create journals; they are not database backups. New contents and old backups are each limited to 16MiB and rejected before mutation if exceeded.

## 事件通道 / Event channel

批准的运行计划可指定 `event_runtime`，指向现有所有者的运行目录。服务只接收和持久保存事件；`ExistingOwnerBridge.consume` 必须由已持有原 supervisor 锁的所有者调用。它核验签名准入，再经认证回环 HTTP 保留一次性事件，通过现有 SingleSlotAdapter、ProcessBackend、预算与签名回执完成离线执行。没有新调度器或租约获取器。

The approved plan may specify the existing owner's `event_runtime`. The service receives/persists events only. The existing owner must call `ExistingOwnerBridge.consume` while holding its original supervisor lease. It validates signed admission, reserves a one-shot event over authenticated loopback HTTP, then uses the existing adapter/backend/budget/signed-receipt chain for isolated execution. No scheduler or lease acquirer is added.

RESERVED 在进程退出、响应丢失或凭据到期后不可重复执行。OWNER_REPORTED 只代表传输记录，执行终态仍为 UNKNOWN；服务回执不能代替账本结算证据。生产原所有者配置未修改；正式 backend 适配与正式维护合同仍待工程闭合。不能把本轮合成签名 worker 的成功当作生产 backend 已接通。

RESERVED events cannot execute again after death, lost responses or credential expiry. OWNER_REPORTED is transport evidence only, with execution terminal UNKNOWN; service receipts never replace signed ledger settlement. Production owner configuration remains unchanged. Formal backend adaptation and maintenance contracts remain engineering work. Synthetic signed-worker success is not production backend integration.

独立操作使用明确的 `OperationId`（64位小写十六进制），同一操作重复调用不重放。已确认回滚结束后，可以用新的显式操作 ID 安装相同包；未知操作不能通过换 ID 绕过全局未决封锁。

Use an explicit 64-character lowercase hex OperationId per approved operation. Repeating an operation never replays it. After confirmed rollback, a new explicit operation ID may install the same package. A new ID cannot bypass another pending/unknown operation.

安装器版本 / Installer version: `1.1.0`. 新安装、升级与恢复均要求独立批准的 `-ApprovedSourceCommit` 与包内 source_commit 完全一致；清单版本不匹配在任何变更前拒绝。
First install, upgrade and recovery require independent `-ApprovedSourceCommit` matching the package source exactly; installer-version mismatch is rejected before effects. Existing receipt v2 remains readable for upgrade ownership; new receipts record source/version. This does not establish formal maintenance authority.
# 1.1.1 维护门禁 / Maintenance gate

中文：当前固定版本尚未接入原生产 Inventory 的实时维护排斥。所有公开安装/升级/恢复/回滚入口的 Execute 在任何目标访问与写入前拒绝；旧仅撤注册脚本亦不能绕过。只读检查和隔离协调器验证保留。安装互斥、历史快照或包SHA不是正式维护权。此修复关闭不安全执行缺口，不代表维护集成已完成或已获安装授权。
English: This pin lacks production-authoritative exclusion with the original Inventory. All public Execute installation, upgrade, recovery and rollback paths reject before target access/effects, including legacy registration-only rollback. Read-only checks and isolated coordinator exercises remain available. Installer mutexes, snapshots and package hashes are not maintenance authority. This closes unsafe admission; it does not complete maintenance integration or authorize installation.
