# U1 固定候选独立审核 / Independent fixed-candidate review

审核源码 / Reviewed source: `70ee72177a40408d5b03a415b3eef3fb51059589`

结论：**OFFLINE_REVIEW_PASSED**。差异及失败路径审查未发现本候选新增的未解决可执行问题；这不代表 RELEASE_READY 或 DEVELOPMENT_COMPLETE。

Result: **OFFLINE_REVIEW_PASSED**. Review of the diff and failure paths found no new unresolved actionable defects in this candidate. This does not establish RELEASE_READY or DEVELOPMENT_COMPLETE.

## 审核与复跑 / Review and independent rerun

独立审查两次源码提交累计全部 15 个变更文件，并复核沿用 ACL helper 及其测试。核对文件事务、协调器、安装入口、事件 mailbox、现有 owner bridge、runtime/bootstrap、包构建及测试变更；并审查 995b109 至最终候选的全部 7 文件差异，逐文件与固定 Git blob 比对（仅归一化 CRLF/LF）。实际磁盘 SHA-256 和 Git blob SHA-256 见同目录 INDEPENDENT_RESULT.json。

Independently reviewed all 15 files changed across the two source commits plus the retained ACL helper and its tests, covering transactions, coordinator, installer, mailbox, owner bridge, runtime/bootstrap, package construction and tests. Also reviewed all seven changed files from 995b109 to the final candidate. Every recorded file matches the fixed Git blob after CRLF/LF normalization. Both disk-byte and Git-blob SHA-256 values are recorded in INDEPENDENT_RESULT.json.

独立执行 17 模块组合：**138 项测试，0 失败，0 错误，0 跳过，228.526 秒，退出码 0**。完整命令及模块列表见结构化报告。未用父代理测试结果替代本次复跑。

Independent execution of 17 modules: **138 tests, zero failures/errors/skips, 228.526 seconds, exit 0**. The structured report records the exact command and module list; this count comes from the reviewer's own run.

## 裁决与恢复路径 / Ruling and recovery paths

接受非对称 ACL：Code Root 保留继承并增加服务 RX；State Root 打断继承，显式保留 SYSTEM、Administrators 和服务账户必要权限。ACL journal 在副作用前持久化意图及原 DACL、写后回读；第二步失败补偿；真实进程退出后仅补偿已知状态，UNKNOWN 或破损 journal 不自动重放。State Root 的初始创建使用安全 DACL，避免先继承普通用户写权限再收紧的窗口。

The asymmetric ACL ruling is accepted: Code Root retains inheritance and adds service RX; State Root disables inheritance and retains explicit required SYSTEM, Administrators and service rights. Durable intent and original DACL precede effects, each effect is read back, second-step failures compensate, and recovery reconciles known state only. UNKNOWN/torn journals never trigger forward replay. State Root is created with a secure initial DACL.

文件事务记录 before/after 哈希或 ABSENT，并持久保存旧字节；升级只修改批准凭据证明的自有文件。回滚前检查全部文件，未知状态保留现场。协调器在安装互斥锁下串联文件、Disabled/Stopped 注册与 ACL；不启动服务。其他未决安装日志封锁新操作。首装、升级、新增、删除、旧文件恢复、ABSENT 删除补偿、进程退出及回滚退出路径均纳入隔离验证。首次安装回滚将事务自建空根恢复 ABSENT；升级保留原有根和状态。

File plans persist before/after hashes or ABSENT and old bytes. Upgrades affect only receipt-proven owned files. Full rollback preflight preserves unknown state. Under installation exclusion, the coordinator sequences files, Disabled/Stopped registration and ACL without starting a service; other pending journals fence new operations. Isolated validation covers first install, upgrades, additions, deletions, restoration, ABSENT compensation and exits during apply/rollback. Fresh-install rollback restores recorded empty roots to ABSENT; upgrades retain existing roots/state.

事件链仅传输授权：原 owner 租约及进程身份、签名 admission、预算与结算仍通过现有 adapter/backend。RESERVED 不因死亡、丢报告或凭据过期重新变为可执行；OWNER_REPORTED 不证明执行终态。离线事件链接入已验证，不能推导生产原 owner 已配置。

The event chain grants transport authority only. Existing-owner lease/process identity, signed admission, budget and settlement remain with the existing adapter/backend. RESERVED is never made executable again after death, a lost report or expired credentials. OWNER_REPORTED is not execution-terminal evidence. Offline integration does not establish production-owner configuration.

## 已修问题复核 / Verification of previously reported defects

- **owned_file_authority — CLOSED**：旧凭据真实字节、独立批准哈希及磁盘字节一致；不接受调用者 owned 字典。

  Actual previous receipt bytes, independent approved hash and on-disk bytes must agree; caller-supplied ownership maps are removed.

- **staging_and_generated_paths — CLOSED**：逐组件拒绝 .u1-new，包与安装器拒绝自生成配置路径；拒绝大小写与祖先碰撞。

  Reject staging components, installer-generated payload paths and case/ancestor collisions.

- **verified_receipts_and_backup_bound — CLOSED**：receipt 仅实际 FILES_APPLIED 回读后可用；新内容与备份各限 16 MiB。

  Receipts require verified applied bytes; payload and backups each have a 16 MiB aggregate bound.

- **historical_rollback — CLOSED**：旧 A 在 B 升级后回滚先全量只读检查，拒绝前不修改 ACL、SCM 或历史日志。

  Historical A rollback after B is rejected by full read-only file preflight before ACL, SCM or historical-journal changes.

- **credential_expiry — CLOSED**：mailbox 操作返回后再次验证凭据；reserve 期间过期返回 401，保持 RESERVED 且不释放事件。

  Authentication is repeated after mailbox operations; expiry during reserve returns 401 and preserves RESERVED without releasing event bytes.

## 最终补丁复核 / Final patch verification

- **fresh_roots_absent — CLOSED**：仅按记录身份清理本事务新建空目录和 Code/State 新根；升级保留原根状态；早期未准备文件计划也由安装日志补偿。

  Only identity-recorded empty transaction directories and fresh roots are removed; upgrades preserve old roots/state; install-journal compensation handles early exits before file preparation.

- **cleanup_intent_exit_recovery — CLOSED**：目录、Code 与 State 删除意图和效果后共六个真实进程退出点恢复通过；ROOT_REMOVE_INTENT 下根尚存在可继续安全补偿。

  Six actual process-exit cut points at directory/Code/State removal intent and effect recover successfully, including ROOT_REMOVE_INTENT with a still-present root.

- **explicit_new_operation — CLOSED**：相同包回滚完成后可用新显式 OperationId 再首装；UNKNOWN 未决操作仍全局封锁。

  A fresh explicit OperationId permits the same package after confirmed rollback; pending UNKNOWN operations remain globally fenced.

新增清理测试包含删除意图与效果后的六个真实退出 cut 点；另外验证 CODE_CREATE_VERIFIED、STATE_CREATE_VERIFIED 的早期退出、未知 State 数据在 ACL/SCM 前停止，以及相同包新操作首次安装。实测 138 项是最终 SHA 的独立完整复跑，不继承中间候选计数。

New cleanup coverage includes six real exit cuts after removal intent/effect, early CODE_CREATE_VERIFIED and STATE_CREATE_VERIFIED exits, unknown state stopping before ACL/SCM, and the same package installed under a new operation. The 138-test result is an independent complete run on the final SHA.

中间候选 995b10947ac21c56b43eee0b08fc710ce6cd6701 的 135 项/116.753 秒仅保留历史归属，已被本候选取代。

The intermediate 995b10947ac21c56b43eee0b08fc710ce6cd6701 result (135 tests/116.753 seconds) is historical and superseded.

## 隔离边界与交付阻断 / Isolation limits and delivery blockers

真实 Windows DACL 测试仅作用于临时目录，以当前用户 SID 代替生产服务 SID；测试替换 audit-root/journal 的 SYSTEM/Admin 信任准入，以便非提升账户运行。生产准入代码另有普通用户目录/文件拒绝测试，以及合成受信描述符正反例。协调器测试使用真实 PowerShell 协调逻辑、真实临时文件和真实子进程退出，SCM、ACL adapter、管理员准入及固定根路径在 fixture 中替换；不能把它称为真实生产安装测试。

Real Windows DACL tests operate only in temporary directories and substitute the current-user SID for the service SID. Audit-root/journal SYSTEM/Admin admission is replaced for non-elevated testing; production admission is separately tested against ordinary-user fixtures and synthetic trusted/untrusted descriptors. Coordinator tests use real PowerShell flow, temporary files and actual process exit, with fixture replacements for SCM, ACL adapter, elevation admission and fixed roots. They are not production installation tests.

本轮未修改生产 ACL、创建生产目录、注册/启动生产服务、修改 Inventory 或写生产数据库。未验证现场 ACL、真实服务 SID、生产 SCM、生产后端或自然业务验收。

No production ACL, directory, service registration/start, Inventory or production-database mutation was performed. Site ACLs, the real service SID, production SCM/backend and natural business acceptance remain untested.

以下是已知交付阻断，不能登记为已完成：

The following delivery blockers remain open:

- 正式维护排斥租约尚未由安装器强制校验。

  Formal maintenance/exclusion lease enforcement is not implemented in the installer.

- 生产 backend 协议适配尚未闭合；本轮签名 worker 是隔离测试。

  Production backend protocol adaptation remains incomplete; the signed worker is an isolated fixture.

- 原生产 Inventory owner 配置未修改，实际生产事件链未验证。

  The original production Inventory owner configuration is unchanged; the production event chain is unverified.

正式发布、部署和生产验收必须单独闭合；本报告只批准所列固定源码的离线审核范围。

Formal release, deployment and production acceptance require separate closure. This report approves only the stated fixed source within the offline review scope.
