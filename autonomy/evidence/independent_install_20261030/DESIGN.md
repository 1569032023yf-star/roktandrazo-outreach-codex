# 独立禁用宿主安装路径 / Independent disabled-host installation path

## 决策与范围 / Decision and scope

中文：选择独立安装路径，旧生产发布器不扩权。WorkBuddy 固定证据见 `../workbuddy_p1_consumption_20261030/source/U1_P1_COMPAT_EVIDENCE_20261030.md` 第3节：仅13个精确既有.py路径；新增目标、缺席备份、删除回滚均不支持。独立路径只允许精确批准包中的.exe/.json/.cs/.ps1，非任意上传或命令入口。首次安装限全新专用目录，既有目录拒绝；升级另立合同。本设计解决交付路线选择，尚非安装实现或生产批准。

English: Choose a separate installation path without expanding the legacy publisher. Section 3 of the pinned WorkBuddy evidence establishes the existing-file/.py-only restrictions and absence/deletion gaps. The new path accepts only exact approved package entries, never arbitrary uploads or commands. First installation requires absent dedicated roots; upgrades need a separate contract. This is a delivery-path design, not an implemented installer or production approval.

## 固定资产与权限 / Assets and authority

中文：复用 disabled_host_package.py、现有真实编译包装器及依赖指纹。代码根固定 C:\Program Files\RoktU1Bridge\v1；状态根 C:\ProgramData\RoktU1Bridge；服务 RoktU1Bridge，身份 NT SERVICE\RoktU1Bridge，Disabled/Stopped。不装任务、不监听8791、不派发Inventory、不写生产DB、不注入代理、不发信。SYSTEM仅为受保护目录的管理ACL，不是执行账户。现有 Install/Rollback-DisabledHost.ps1 是候选参考实现，不能按本设计直接执行：尚缺持久安装日志、原Inventory维护租约的可信实时验证和原子目录发布。

English: Reuse the existing package builder, compiled wrapper and dependency fingerprints. Fix the code/state roots and virtual service identity above, with Disabled/Stopped registration. No task, listener, dispatch, database write, proxy change or mail is included. SYSTEM is an administrative ACL principal, not the execution identity. Existing scripts are reference candidates only: durable install journaling, live original-Inventory maintenance-lease validation and atomic directory publication remain implementation gates.

## 事务与恢复合同 / Transaction and recovery contract

中文：正式执行器须在任何写入前验证外部批准的源码/包/脚本SHA、依赖指纹、管理员单次授权、维护窗口、原Inventory1784775229336及原排他锁租约。安装互斥 Global\RoktU1BridgeInstall 不能替代原锁；租约必须覆盖最终检查至回读。凭待审包自报的哈希不构成批准。目标全祖先拒绝重解析点，检查受保护父目录及同卷；目标code/state/service已存在一律停止，不接管。维护租约协议未正式提供时 Execute 必须不可达。

English: Before any mutation the executor must verify external approval of source/package/script hashes, dependency fingerprints, one-shot administrative authorization, maintenance window and the original Inventory/exclusion lease. The installer mutex does not replace the Inventory lock; the lease spans final checks through readback. Self-reported hashes cannot authorize installation. Reject reparse ancestors, unsafe parents, different-volume staging and any existing target/service. Execute remains unreachable without the formal lease protocol.

中文：独立受保护安装审计目录须先以 CREATE_NEW 写入并flush持久操作日志，记ABSENT前态、包SHA、operation_id、租约绑定；不得把日志藏在可能未创建的代码目录。阶段 PREPARED → STAGED（同卷新目录全量复制、逐文件校验、受保护ACL）→ PUBLISHED（原子rename首次发布）→ REGISTERED_DISABLED（创建虚拟账户服务、设置code RX/state Modify并验证有效ACL）→ VERIFIED（Stopped/Disabled/精确image/account/hash回读）。每次副作用前记意图，后记回执；日志/回执不一致转UNKNOWN，重启只status，不自动重放。注册期间ACL失败时仅在精确归属、仍Stopped且租约有效时撤销注册，否则停留并保全。

English: Create and flush a CREATE_NEW operation journal in a separately protected audit directory before mutation, recording ABSENT, package hash, operation ID and lease binding. PREPARED → STAGED (same-volume copy, hash and protected ACL validation) → PUBLISHED (atomic first directory rename) → REGISTERED_DISABLED (virtual-account registration and effective ACL checks) → VERIFIED (Stopped/Disabled/image/account/hash readback). Record intent before and receipt after each effect. Inconsistency becomes UNKNOWN: restart performs status only, never automatic replay. ACL failure permits registration removal only with exact ownership, Stopped state and valid lease; otherwise preserve everything.

## 回滚选择 / Rollback choice

中文：独立路径明确采用“撤销注册、保留不可变代码及全部状态”，不依赖旧发布器删除回滚。它使新宿主失去入口且保留审计，并不恢复安装前磁盘完全缺席。精确receipt+hash+account+image、Stopped、原维护租约与互斥全部成立才可Disable/Delete注册并回读；服务不存在只标ABSENT，绝不据此删除文件。代码、安装日志、凭证和全部slot/UNKNOWN/预算/资格历史一律保留。日后磁盘清理由独立批准的精确清单执行，本轮不提供recursive delete；无法证明所有权时STOP_AND_PRESERVE。旧执行器不读取新账本、不恢复旧DB覆盖新历史；恢复旧执行权另行guard/schema兼容审查。

English: Roll back by removing only the disabled registration while retaining immutable code and all state. This avoids dependence on deletion rollback in the legacy publisher, but does not restore disk absence. Require exact receipt/hash/account/image, Stopped state, original maintenance lease and mutex before Disable/Delete/readback. An absent service never authorizes file deletion. Preserve code, journals, credentials, slots, UNKNOWN outcomes, budgets and qualification history. Future cleanup needs a separately approved exact manifest; no recursive deletion is provided. Uncertain ownership means STOP_AND_PRESERVE. Never restore an old database over new history; old authority restoration needs guard/schema compatibility review.

## 验收及最小一次性授权 / Acceptance and minimum one-shot approval

中文：本轮离线plan消费者只验证缺席前态/身份/中断分类且恒拒绝执行，不证明Windows安装。进入管理员申请前还必须：实现上述日志/租约/原子发布；隔离Windows实测每阶段退出、ACL失败、注册回执丢失、foreign路径、junction、SCM延迟删除及重试拒绝；固定源码包独审。之后仅申请在指定窗口、固定SHA下创建两个专用目录与审计目录、应用最小ACL、创建一个Disabled虚拟账户服务及验证/撤销该注册；不批准Start/Auto、重启、注销、出口或原Inventory权威切换。这些另需生产方案及授权。真实无人登录、8791持续运行及增长均UNKNOWN。

English: The offline plan consumer validates absence/identity/interruption classification and always denies execution; it does not prove Windows installation. Before requesting elevation, implement the journal/lease/atomic publication and test stage exits, ACL failures, lost registration receipts, foreign paths, junctions, delayed SCM deletion and retry rejection in isolated Windows, then independently review a fixed source bundle. Request only the fixed-window/fixed-SHA creation of dedicated code/state/audit roots, minimal ACLs, one Disabled virtual-account service and its verification/registration removal. Start/Auto, reboot/logoff, egress and Inventory authority transfer remain excluded and need separate authority. Unattended operation, persistent8791 and growth remain UNKNOWN.
