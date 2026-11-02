# U1 ACL 裁决与安装器修复 / ACL ruling and installer repair

日期 / Date: 2026-11-02（Asia/Taipei）
固定源码 / Fixed source: `0db17b51d8ce464f1f57dd5ef40d0df266dcf3f8`
裁决 / Ruling: [Comment 6520202418](https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/2#issuecomment-6520202418)，接受 / ACCEPTED。

中文：Code Root `C:\Program Files\RoktU1Bridge\v1` 保留继承和原ACE，只添加服务 SID ReadAndExecute。State Root `C:\ProgramData\RoktU1Bridge` 保护DACL，仅保留 SYSTEM/Administrators FullControl 和服务 SID Modify。原评论内部写了自身编号6520177690，本次以实际GitHub ID 6520202418绑定，RULING.json保留原文。SUPERSEDES=U1_P1_COMPAT_EVIDENCE_20261030:1g仅就建议性质而言，历史候选行为描述仍有效。

English: Preserve code-root inheritance/existing ACEs and add service SID ReadAndExecute only. Protect the state DACL with SYSTEM/Administrators FullControl and service SID Modify only. The comment's internal self-ID is6520177690; this delivery binds actual GitHub ID6520202418 and preserves the original in RULING.json. Supersession of U1_P1_COMPAT_EVIDENCE_20261030:1g concerns its interpretation as a recommendation only; the historical description remains valid.

中文：新助手Acl-Transaction.ps1纳入包manifest哈希，固定文件句柄后才加载。PREPARED在修改前持久记录operation_id、manifest、两个根的before/after DACL。每步先写APPLY_INTENT，修改后精确回读并写VERIFIED。失败先核对两个实际结果，再逆序记录ROLLBACK_INTENT、补偿和验证。日志使用CreateNew、独占句柄、WriteThrough及Flush(true)，旧日志不覆盖。日志位于独立管理员审计根C:\ProgramData\RoktU1InstallAudit；根及打开日志句柄均校验owner/ACE，并拒绝重解析路径。安装器不自动创建或修补审计根。

English: Acl-Transaction.ps1 is included in the package manifest hash and pinned before loading. PREPARED durably records operation_id, manifest and both before/after DACLs before mutation. Each APPLY_INTENT precedes mutation; exact readback precedes VERIFIED. Failure prechecks both observations, then records reverse-order ROLLBACK_INTENT, compensation and verification. Journals use CreateNew, exclusive handles, WriteThrough and Flush(true), never overwriting old operations. Journals reside in the separate administrator audit root C:\ProgramData\RoktU1InstallAudit. Root and open-file owner/ACEs are checked and reparse paths rejected. The installer never implicitly provisions or repairs this root.

中文：显式-RecoverAcl -Execute只观察并补偿已知before/after状态，不重放安装或APPLY。异常ACL、截断日志、错误manifest或不可信日志停止写入，保留证据供对账。回滚失败也保留记录，不自动重试。恢复拒绝已完成安装凭据；已存在服务必须是相同账户/映像、Disabled且Stopped。ACL事务成功后安装器若发生后续错误，也执行已记录补偿。

English: Explicit -RecoverAcl -Execute observes and compensates known before/after states only, never replaying installation or APPLY. Unexpected ACLs, truncated journals, wrong manifests or untrusted journals stop writes and preserve evidence for reconciliation. Rollback failure retains records without automatic retry. Recovery rejects completed-install receipts; an existing service must match account/image and be Disabled/Stopped. An installer error after ACL commit also triggers recorded compensation.

中文：初审发现状态根默认继承写权限会暴露预植窗口，现先持久记录ABSENT到受限DACL的STATE_CREATE_INTENT，再以.NET Framework带DACL的原子创建API仅授予SYSTEM/Admin，回读后写STATE_CREATE_VERIFIED。双根事务随后添加服务Modify。创建中断或竞态保留证据并停止，不自动重建或删除。补偿恢复的是安全初始DACL，不恢复任何数据库快照。

English: Initial review found that default inherited state writes exposed a preplanting window. Creation now persists STATE_CREATE_INTENT from ABSENT to a restrictive DACL, uses the .NET Framework atomic directory-with-DACL API with SYSTEM/Admin only, then records STATE_CREATE_VERIFIED after readback. The two-root transaction subsequently adds service Modify. Interrupted creation or races retain evidence and stop without automatic recreation/deletion. Compensation restores the secure initial DACL, never a database snapshot.

验证 / Validation:

- 主组合 / Primary: **61 tests, 0 failures/errors/skips, 32.572s**，见VALIDATION.json与TEST_OUTPUT.txt。工作树CRLF与Git blob LF除行尾外一致，两套SHA256均已记录。Worktree CRLF and Git LF match except line endings; both SHA256 sets are recorded.
- 独审 / Independent: **39+2 tests passed**；最终差异及失败路径审查通过，三个初审安全问题已修复。见INDEPENDENT_REVIEW.md和INDEPENDENT_TEST_RESULT.json。Final diff/failure-path review passed with three initial security findings closed.
- 覆盖 / Coverage: 双根成功、第二步失败、首步回读后退出、第二步意图后退出、第二次写入后回读前退出、回滚中退出、回滚失败恢复、持久化失败、未知ACL、截断日志、错误manifest、禁止重放、原子创建、信任门禁及恢复准入。Both-root success; second-step failure; exits after first readback, second intent and second write before readback; exit during rollback; rollback-failure recovery; persistence failure; unknown ACL; truncated journal; wrong manifest; no replay; atomic creation; trust and recovery gates.

中文：测试使用真实Windows临时目录DACL及日志。当前用户SID替代服务SID，非提权集成夹具替换审计根/文件信任门禁，另有真实普通用户拒绝及合成SYSTEM/Admin正反例。没有执行完整生产安装器、服务注册/启动、生产ACL、生产目录创建、Inventory修改或生产数据库写入；未证明整机断电或完整安装事务恢复。本候选未重跑全量回归，旧包及旧回归不能替代本候选验收。测试清理曾因.NET仅持久化标记修改的ACL而报错，修复后主组合和独审均通过。

English: Tests use real Windows temporary-directory DACLs and journals. Current-user SID substitutes for service SID; unprivileged integration fixtures replace audit-root/file trust gates, with separate real ordinary-user rejection and synthetic SYSTEM/Admin positive/negative cases. The complete production installer, service registration/start, production ACLs/directories, Inventory changes and production database writes were not executed. Whole-machine power loss and complete-install transaction recovery remain unproven. No full regression was run for this candidate; older packages/regressions do not accept this candidate. A test-cleanup failure caused by .NET persisting only modified ACL sections was repaired before successful primary and independent reruns.

中文：本轮离线范围开发与独审完成，发布清单不可执行。后续实际安装须另行授权并确认批准审计根、实际身份/登录权、精确包兼容、互斥窗口及完整安装门禁；本轮不申请或执行。未知创建结果、未知ACL或损坏日志必须明确对账，不用自动重试解决。没有重复索要WorkBuddy环境证据。

English: Scoped offline development and independent review are complete; the release checklist is non-executable. Future installation requires separate authority, approved audit root, actual identity/logon rights, exact package compatibility, exclusion window and complete installation gates; none is requested or executed here. Unknown creation, unknown ACLs or damaged journals require explicit reconciliation, never automatic retry. No duplicate WorkBuddy environment evidence was requested.

SCOPED_DEVELOPMENT_COMPLETE=true; SCOPED_REVIEW_PASSED=true; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; allow_install=false; allow_dispatch=false; CURRENT_SAFE=UNKNOWN; BUSINESS_GROWTH=UNKNOWN.

自检 / Self-check: 中英双语、无秘密、已区分执行/未执行事项、风险和下一步，不将离线验证当作生产验收。Bilingual, no secrets, executed/unexecuted work, risks and next steps distinguished; offline validation is not production acceptance.
