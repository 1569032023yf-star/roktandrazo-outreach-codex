# 发布器维护排斥独立范围审核 / Publisher maintenance scoped review

固定源码 / Fixed source: `a90b28fdfb7da4caca97fab33b2d414aee8e1919`

结论：**OFFLINE_SCOPED_REVIEW_PASSED**。本范围已报问题关闭，无新增可确认阻断。此结论不代表完整现场调用链审核通过、可安装或 RELEASE_READY。

Result: **OFFLINE_SCOPED_REVIEW_PASSED**. Reported defects in this scope are closed, with no new confirmed actionable findings. This does not approve the complete site call chain, installation or RELEASE_READY.

## 审核范围与实现证据 / Scope and implementation evidence

独立检查开发副本 executor、来源绑定、Inventory admission、维护会话、内部 PS 协调器与测试。来源原文件只读 SHA 与 SOURCE_BINDING 相符，候选 SHA 也相符；现场原文件未修改。JSON 记录逐文件实际字节及 Git blob SHA-256，并确认与固定提交一致（换行归一化）。报告时 HEAD 已有测试编排修复提交，所列被审文件仍与 a90b28f 完全对应，不将编排变更视作已复跑源码。

Reviewed the executor development copy, source binding, Inventory admission, maintenance sessions, internal PowerShell coordinator and tests. Read-only source/candidate hashes match SOURCE_BINDING. The original site file is unchanged. JSON records disk/Git-blob SHA-256 and fixed-source equality after newline normalization. HEAD later advanced for test orchestration, while every listed reviewed file still matches a90b28f; that later change is not represented as independently tested source.

共享 marker 检查位于原发布器 BEGIN IMMEDIATE 中、旧锁接管与替换之前；Inventory 与 publisher 共用持久排斥。获取无 stale override，跨日期未决原锁阻塞。异常不释放；invocation 墓碑禁止重放。最终核验凭据与释放同事务提交；commit 前失败保持排斥，commit 成功但返回丢失保持 RELEASED 记录且拒绝重复安装。公开 Install-DisabledHost.ps1 Execute hard gate 未解除。

Shared-marker admission runs in the original publisher BEGIN IMMEDIATE before stale-lock handling and replacements. Inventory and publisher share persistent exclusion; acquisition never overrides old/unknown holders across dates. Errors retain exclusion and invocation tombstones prevent replay. Final proof and release commit atomically; pre-commit failure stays held, and committed-but-lost replies remain observable as RELEASED without reinstalling. The public installer Execute hard gate remains intact.

## 已报问题 / Reported defects

- **action_binding — CLOSED**：实际动作绑定与多 flags 拒绝。

  Actual action binding and rejection of multiple action flags.

- **atomic_acquire_context — CLOSED**：marker、墓碑和 HELD 完整上下文同事务提交，事务内退出无孤标记。

  Marker, tombstone and complete HELD context commit together; transaction death leaves no orphan marker.

- **explicit_partial_compensation — CLOSED**：同一维护权下显式补偿，需旧进程停止证明；不重放正向安装。

  Explicit compensation retains exclusion and requires prior-process termination proof, without forward replay.

- **handoff_late_transition — CLOSED**：父子交接、状态机与最终释放前态在写事务中复验，迟到父回执不可释放。

  Handoff, transitions and final release recheck prior state in write transactions; late parent replies cannot release.

- **handoff_child_held_cut — CLOSED**：handoff 提交后、child intent 前真实退出43后，HELD 子可用新 recovery_id 恢复。

  Real exit 43 after handoff commit and before child intent permits fresh explicit recovery from HELD.

## 独立测试及边界 / Independent tests and limits

独立分进程复跑 **29 项，0 失败/错误/跳过**：publisher/session/Inventory 26 项，1.412 秒；PS 错动作、多动作、缺维护权及文件后丢维护权等三项方法，4.974 秒。完整命令见 JSON。覆盖 SQLite 竞争唯一获胜、原四条 apply/rollback 路径在绿灯前检后拒绝副作用、真实进程退出、原子获取、部分文件补偿、commit 失败/回执丢失、父子交接确定性交错及 HELD child cut。

Independently reran **29 passing tests, zero failures/errors/skips**: 26 publisher/session/Inventory tests in 1.412s, and three PowerShell methods covering wrong/multiple actions, absent authority and lost authority after files in 4.974s. Commands are in JSON. Coverage includes racing SQLite admission, all four original apply/rollback paths refusing effects after green preflight, process death, atomic acquisition, partial compensation, commit failures/lost acknowledgements, handoff interleaving and the HELD-child cut.

最初混合进程因 bd_db 导入开发 subprocess guard，正确阻断两项 pwsh，随后保持 guard 不变并分进程复跑；受限尝试不计为通过。所有测试使用临时 SQLite、临时文件与隔离进程；PS 使用 SCM/ACL/管理员准入替身，publisher 测试替换 seal/config 前检。真实进程 poll/wait 与合成身份摘要、注入 verifier 只证明隔离逻辑，不能替代正式进程适配与独立现场终态核验。

An initial mixed process imported the development subprocess guard through bd_db and correctly blocked two pwsh tests. The unchanged guard was retained and tests reran separately; that attempt is not passing evidence. Tests use temporary SQLite/files and isolated processes. PowerShell uses SCM/ACL/admin doubles; publisher tests replace seal/config preflight. Real poll/wait checks plus synthetic identity digests/injected verifiers establish isolated behavior, not formal process adaptation or independent site-terminal verification.

## 尚未闭合 / Outstanding integration

- 正式入口到受控安装进程的适配器、真实进程创建身份及停止/存活复验未完成。

  The supported publisher-to-controlled-installer adapter and real process identity/termination revalidation are incomplete.

- 独立目标文件/安装日志/真实 SCM/ACL 最终核验器未完成；注入 callback 不等于现场核验。

  The independent target/journal/real SCM/ACL final verifier is incomplete; callback injection is not site verification.

- 现场 seal 刷新、通道变更授权和原 owner 接线未完成。

  Site seal refresh, channel-update authorization and original-owner wiring remain incomplete.

保持 `allow_install=false; allow_dispatch=false; SMTP=false; RELEASE_READY=false`。本轮未写生产数据库、操作生产服务/ACL、修改现场 executor 或原 owner 配置。不得据此开始实际无人值守或生产验收。

Keep installation, dispatch, SMTP and RELEASE_READY false. No production DB, service/ACL, site executor or original-owner configuration was modified. This evidence does not authorize unattended production or production acceptance.
