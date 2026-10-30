# U1 P0 固定候选 — 只读 P1 兼容证据包 / U1 P0 Fixed Candidate — Read-Only P1 Compatibility Evidence Package

- 生成时间 / Generated: 2026-10-30T14:35:00+08:00 (2026-10-30T06:35:00Z)
- 产出方 / Produced by: WorkBuddy read-only lane
- 机器可读版本 / Machine-readable: `U1_P1_COMPAT_EVIDENCE_20261030.json`（同目录 / same directory）
- 请求来源 / Request: Issue #2 comment `6513015427`（2026-10-30 09:54:08 +08）
- 执行指令 / Directive: Issue #2 comment `6516441030`（2026-10-30 14:23:51 +08）

## 固定输入 / Pinned inputs

| 项 / Item | 值 / Value |
|---|---|
| `SOURCE_SHA` | `d7d424c120281981e70753ea1c15fe130134929f` |
| `EVIDENCE_PACKAGE_SHA` | `c7f2ac15391f3fe3522d3e218650749474b39188` |
| `PACKAGE_MANIFEST_SHA256` | `1011e76faa2bedf793991f0860d87cc53e2f49d3a0af76cf49b4391bc7e4a3c0` |
| 包完整性 / Package integrity | `DEV_PACKAGE.zip` 12297 bytes，zip sha256 `2575e0d0…10fd95`；**7/7** 声明文件哈希一致；内嵌 `manifest.json` SHA256 **等于** `PACKAGE_MANIFEST_SHA256` |
| 候选架构 / Candidate arch | `service/RoktU1Bridge.exe` PE machine `0x8664`（x64 确认 / x64 confirmed） |

## 总览 / Overview

**整体完成数量：2 / 5 项完全通过，3 / 5 项部分完成（PARTIAL）。全部阻断项 0。**
**Overall: 2 of 5 items fully verified, 3 of 5 PARTIAL, 0 wholly blocked.**

| # | 项目 / Item | 判定 / Verdict |
|---|---|---|
| 1 | 身份、虚拟账户能力、生效 ACL 与最小增量 / Identity, virtual account, effective ACL, minimal delta | **PARTIAL** |
| 2 | 7877 非交互出口 / 7877 non-interactive egress | **PARTIAL** |
| 3 | 运行时指纹与发布器四类能力 / Runtime fingerprints + four publisher capabilities | **PARTIAL** |
| 4 | Inventory 唯一执行权与锁合同 / Inventory sole authority and lock contract | **PASS** |
| 5 | v2 恢复守卫双向迁移与 STOP_AND_PRESERVE / v2 guard bidirectional migration | **PASS** |

> 明确不计入：本机 Python / SQLite / .NET 指纹 PASS **不等于**发布器验收，也**不等于**主机或生产验收。
> Explicitly not counted: a local Python / SQLite / .NET fingerprint PASS is neither publisher acceptance nor host or production acceptance.

---

## 1. 身份与 ACL / Identity and ACL — PARTIAL

**中文。** 本通道执行身份为 `RAKTROZO\15690`（SID `S-1-5-21-…-1001`），`IsElevated=False`，完整性级别 Medium，`BUILTIN\Administrators` 在令牌中为**仅拒绝**组。主机为 Windows 11 家庭版 Build 26200，工作组 `WORKGROUP`，非域成员。

虚拟账户能力在 SID 层已可证：`NT SERVICE\TrustedInstaller` 解析为 `S-1-5-80-956008885-…`，`NT SERVICE\ALL SERVICES` 解析为 `S-1-5-80-0`，说明本机 SERVICE 类型 SID 命名空间可用。`NT SERVICE\RoktU1Bridge` 当前**不可解析**——这是正确行为，虚拟账户 SID 随服务创建而生成；候选安装脚本 `Install-DisabledHost.ps1` 先建服务（第 95 行）后翻译账户（第 98 行），顺序正确。

父目录继承基线（**INHERITED_BASELINE**，不是目标目录生效 ACL）：`C:\Program Files` 为 TrustedInstaller(F)、SYSTEM(M)、Administrators(M)、Users(RX)，Users **无 WD/AD**，因此非提权无法在此新建目录；`C:\ProgramData` 为 SYSTEM(F)、Administrators(F)、CREATOR OWNER(F)、Users(RX) 加 `Users:(CI)(WD,AD,WEA,WA)`，允许用户在其下新建子目录。

最小 RX/Modify 增量只能标 **PROPOSED_ONLY**：候选脚本用 `SetAccessRuleProtection(true,false)` 打断继承，仅保留 SYSTEM Full、Administrators Full、服务 SID 在代码根 `ReadAndExecute`、在状态根 `Modify`（CI+OI）。该提案有意丢弃继承来的 `Users:(RX)`。由于两个目标目录均不存在，这**不是**任何目录的生效 ACL，也**未获批准**。

`SeServiceLogonRight` 无法获取：`secedit /export /areas USER_RIGHTS` 在非提权令牌下返回“权限不足”→ **BLOCKED**，需管理员令牌。

**English.** Executing identity is `RAKTROZO\15690` (SID `S-1-5-21-…-1001`), not elevated, Medium integrity, `BUILTIN\Administrators` is deny-only in the token. Host is Windows 11 Build 26200, workgroup, not domain-joined. The SERVICE SID namespace is proven usable (`NT SERVICE\TrustedInstaller` → `S-1-5-80-956008885-…`, `NT SERVICE\ALL SERVICES` → `S-1-5-80-0`); `NT SERVICE\RoktU1Bridge` is correctly unresolvable until the service exists, and the installer creates the service before translating the account. Parent ACLs are recorded as INHERITED_BASELINE only: `Program Files` grants Users RX without WD/AD (no unelevated directory creation), `ProgramData` additionally grants `Users:(CI)(WD,AD,WEA,WA)`. The RX/Modify delta is PROPOSED_ONLY — the script protects inheritance and keeps exactly three ACEs per root — and is neither an effective ACL nor an approval. `SeServiceLogonRight` is BLOCKED: `secedit` requires an elevated token.

## 2. 7877 非交互出口 / 7877 non-interactive egress — PARTIAL

**中文。** 监听仅 `127.0.0.1:7877`（无外部绑定），属主 `MyClashCore.exe` PID 15344，**SessionId=0**，父进程 PID 6356 `MyClashHelperService.exe`。该助手服务为 `Running`、`StartMode=Auto`、`DelayedAutoStart=False`、`StartName=LocalSystem`、镜像位于 `D:\Clash Plus\MyClashHelperService.exe`。GUI `MyClash.exe` PID 35256 在 **Session 1**，与监听进程分离，不是必需依赖。

回环连通已实测（TcpClient 127.0.0.1:7877 CONNECT_OK）。真实转发也已实测：`gstatic.com/generate_204` → **204**，`api.github.com` → **200**，证明不只是“端口打开”。

**结构性推断（PARTIAL，不是实测）**：内核进程驻留 Session 0 且由开机自启的 LocalSystem 服务派生，生命周期绑服务而非登录桌面；回环为全机范围，因此任意会话下的服务都能访问 7877。

**UNKNOWN**：注销/重启后的实际出口、`D:` 卷未挂载时的后果、GUI 缺席时死节点的恢复。取证会中断本会话或重启主机，故未执行。

另需区分两条出口：本会话 `HTTP_PROXY/HTTPS_PROXY = http://127.0.0.1:63440`（宿主托管），而生产发现链路用 `.env` 的 `SCRAPER_PROXY=http://127.0.0.1:7877`。Session-0 服务不继承用户配置也不继承此 shell 环境，代理值必须由服务定义显式注入。候选本身**不写任何代理代码**，当前无出口需求。

**English.** Listener is loopback-only on 7877, owned by `MyClashCore.exe` PID 15344 in Session 0, parented by `MyClashHelperService.exe` PID 6356 — an Auto-start, non-delayed, LocalSystem service at `D:\Clash Plus\MyClashHelperService.exe`. The GUI runs in Session 1 and is not the listener. Loopback connect succeeds, and real forwarding is proven (204 / 200), not just an open port. Unattended availability is a PARTIAL structural inference — Session 0 plus service-owned lifetime plus machine-wide loopback — and logoff/reboot, the `D:` volume dependency and GUI-less node recovery remain UNKNOWN because measuring them would terminate this session or reboot the host. Two distinct egress configurations exist (host shell `63440` vs production `SCRAPER_PROXY=7877`); a Session-0 service inherits neither, so any proxy must be injected explicitly. The candidate itself contains no proxy code.

## 3. 运行时与发布器 / Runtime and publisher — PARTIAL

**中文。** 运行时指纹沿用本轮会话已取得的观测，不再重复采样、且**不计为**主机验收：Python 3.13.0、SQLite 3.45.3、时区 `+0800`、AMD64；候选声明的 5 个 .NET Framework 4 x64 DLL SHA256 **5/5 一致**；`python.exe` SHA256 与 Codex `LOCAL_RUNTIME_OBSERVATION` 一致。

发布器四项能力逐项结论：

1. **新增文件** —— **不支持**。`registry._apply_checks` 对非文件目标返回 `{feasible:false, reason:"target_absent"}`，令 `deployable=false`；`executor.op_apply_multi` 在写备份前先 `target.read_bytes()`（第 990 行），目标不存在会在任何写入前中止。
2. **目标原先不存在时的备份表示** —— **不存在该表示**。字面量 `ABSENT` 仅存在于清单词汇（`registry.py:155`）与 attest 分支（`247-249`）；备份步骤是对既有文件的无条件字节复制（`executor.py:1002-1012`），备份目录里从不写“缺席哨兵”。
3. **原子替换** —— **源码层支持**。同卷临时文件 + 写入 + `fsync` + 复制原 DACL + `os.replace`，随后逐文件复核 SHA 与字节数；任一失败整体回滚（`executor.py:1014-1031`）。
4. **删除回滚** —— **不支持**。`op_rollback_multi` 只从 `.before.bak` 用 `os.replace` 还原，并要求 `current==declared_after` 且 `backup==declared_before`；没有任何分支删除“由本次 apply 新建的文件”（`executor.py:1124-1174`）。

配置层证据：`allowed_scope.rules.extensions=[".py"]`，拒绝模式含 `*.json`、`*.env*`、`*.db`、`*.pem`、`*.key` 等；路径白名单为生产根下 13 个精确 `.py`；`max_files_per_release=6`，`max_patch_bytes=262144`。`channel_config` 现有 4 个已登记发布、3 个可部署，**没有一个**指向非 `.py` 路径或尚不存在的文件。

**结论**：候选负载为 `config/host.json`、`runtime/*.json`、`service/RoktU1Bridge.cs`、`service/RoktU1Bridge.exe` 与 2 个 `.ps1`——**7 个文件中 0 个是 `.py`**。现发布器在架构层面**无法承载该候选的任何文件**，这不是门禁未通过，而是通道的表达能力不足。

**English.** Runtime fingerprints are carried over from earlier sampling in this session and are explicitly not host acceptance: Python 3.13.0, SQLite 3.45.3, tz +0800, AMD64, 5/5 declared .NET Framework 4 x64 DLL hashes matched, `python.exe` matches Codex's local observation. Of the four requested publisher capabilities exactly one is supported: atomic replacement (same-volume temp + fsync + DACL copy + `os.replace` + post-verify). Exact new files are unsupported (`target_absent` forces `deployable=false`; the apply path reads the target before it can back it up). There is no absence representation in backups — `ABSENT` exists only as manifest vocabulary. Deletion rollback is unsupported: rollback only restores `.before.bak` and has no branch that deletes a file created by the apply. Config layer: extensions `[".py"]`, `*.json` denied, a 13-path `.py` whitelist, max 6 files and 256 KiB patch. The candidate payload contains 0 of 7 `.py` files, so the current publisher cannot carry any part of it — a capability gap, not a failed gate.

## 4. Inventory 唯一执行权与锁合同 / Inventory sole authority and lock contract — PASS

**中文。** 唯一 ACTIVE Inventory 为 `automation-1784775229336`（`FREQ=HOURLY;INTERVAL=6`）；另外两个 Inventory 自动化 `1785720738893`、`1785720747436` 均为 `PAUSED`；库内共 30 个自动化。`channel_config.inventory_automation_id` 与之一致。

锁键形状双方一致：编排器在 `bd_orchestrator.py:451` 调用 `acquire_run_lock(f'inventory:{business_date}')`、`:549` 释放；`bd_db.acquire_run_lock` 拼出 `run_lock:daily_outreach:{date_str}`（`bd_db.py:801`）；通道前缀 `channel_config.lock.key_prefix` 为 `run_lock:daily_outreach:inventory:`。今日实际键 `run_lock:daily_outreach:inventory:2026-10-30` = `released`，`_acquired_at` 05:09:09Z（13:09:09 +08），释放 05:26:30Z，**当前未持锁**。

holder 语义：获取为 `BEGIN IMMEDIATE`，他人持有的有效锁一律不夺取，2 小时陈旧阈值；释放为 `UPDATE … WHERE value=holder`，非持有者无法释放。通道 `executor.py:755-803` 复刻同一语义。

采样时刻生产库 `data/bd_leads.db` `quick_check=ok`，mtime 2026-10-30T13:26:30+08:00，sha256 `4fdc92bd…6358e`（只读，无写入）。

最小宿主缺失能力如实记录：**8791 认证监听 = 不存在**；**Python 执行器 = 不存在**；**生产 backend = 未被引用**（`RoktU1Bridge.cs` 全文无 SQLite、数据库、HTTP 或监听代码，只写一个未签名本地心跳文件）。这支持 Codex 的 `PRODUCTION_INSTALLABLE=false` 判断，本报告不主张任何集成就绪。

**English.** Sole ACTIVE Inventory is `automation-1784775229336` (6-hour interval); the two other Inventory automations are PAUSED; 30 automations exist; the channel config binds the same id. Lock keys agree: the orchestrator passes `inventory:{business_date}` (lines 451/549), `bd_db` builds `run_lock:daily_outreach:{date_str}` (line 801), and the channel prefix is `run_lock:daily_outreach:inventory:`. Today's key is `released` (acquired 13:09:09 +08, released 13:26:30 +08), so the lock is not held. Holder semantics match on both sides (BEGIN IMMEDIATE, never steal a valid lock, 7200s stale, release only by holder). DB `quick_check=ok`, mtime 13:26:30 +08, sha256 `4fdc92bd…`, read-only. Missing capabilities are recorded honestly: no 8791 listener, no Python executor, no backend reference — the C# host writes only an unsigned local heartbeat, which supports `PRODUCTION_INSTALLABLE=false`.

## 5. v2 恢复守卫双向迁移 / v2 recovery-guard bidirectional migration — PASS

**中文。** 被测实现为 `autonomy/lock_recovery.py`（sha256 `e6552960…da7741`，8045 字节，取自 `PINNED_SOURCE.zip @ c7f2ac15`），守卫文件 `supervisor.recovery.lock`，标记字节精确为 `b'rokt.recovery-guard.v2\n'`（23 字节）。

隔离夹具（沙箱目录 `…\Temp\u1fixture`，未触碰任何生产账本/锁/数据库）**10/10 PASS**，另 1 项观察：

- C1 legacy 空守卫 → `LEGACY_OR_UNKNOWN_RECOVERY_GUARD`，且文件被**原样保留**（0 字节未被删除或改写）
- C2 截断标记、C3 仅换行 → 同样拒绝
- C4 全新运行时 → 发布精确 23 字节标记
- C5 v2 标记存在后，legacy `O_CREAT|O_EXCL` 获取 → `FileExistsError`（legacy 执行器安全失败）
- C6 legacy `schema_version=1` 的 `supervisor.lock` → `LOCK_IDENTITY_UNPROVEN`（不可静默接管）
- C7 空 legacy `supervisor.lock` → 阻止 v2 获取且保持 0 字节未被覆盖
- C8 临界区异常中止后守卫文件仍在（未被 unlink）
- C9 跨进程竞争 → 第二名 `RECOVERY_GUARD_BUSY`
- C10 `exclusive_lock` 写入 `schema_version=2`，干净退出只删除自己的锁
- C11（观察）同一进程内嵌套 `_guard()` → `RECOVERY_GUARD_BUSY`。守卫**不可重入**；生产组合只在最外层加锁并传租约（`single_slot_adapter._lock`、`cancellation_recovery._owner` 均不嵌套），故这是对未来调用方的约束，不是现存缺陷。

`STOP_AND_PRESERVE` 已行为化验证：`rollback_admission` 要求 10 个强制标志全 True（含 `preserve_ledger`）且 `restore_old_database is False`，并要求未决槽位/预算全为 0，且**从不返回** `allow_dispatch=True`。夹具 8/8 断言 PASS、`dispatch_ever_allowed=false`。代码锚点 `rollback_admission.py:46-47`。守卫路径本身无账本或数据库 IO，`recover_lock` 仅在做完身份证明后 unlink `supervisor.lock`。

生产侧迁移前提干净：`deploy-channel\state\supervisor.recovery.lock` **不存在**，只有遗留 `supervisor.lock`（64 字节，2026-10-29 22:40），即**生产中没有需要迁移的 legacy 空标记**。

**English.** The implementation under test is `autonomy/lock_recovery.py` (sha256 `e6552960…`, 8045 bytes, from `PINNED_SOURCE.zip @ c7f2ac15`) with guard file `supervisor.recovery.lock` and exact marker `b'rokt.recovery-guard.v2\n'`. An isolated fixture scored 10/10 PASS: legacy empty guard rejected and preserved byte-for-byte; truncated and newline-only markers rejected; fresh runtime publishes the exact marker; legacy O_EXCL acquisition fails safely once the v2 marker exists; a legacy schema-v1 lock yields `LOCK_IDENTITY_UNPROVEN`; an empty legacy lock blocks v2 and stays untouched; the guard survives an aborted critical section; a second process gets `RECOVERY_GUARD_BUSY`; `exclusive_lock` writes schema_version 2 and removes only its own lock. One observed constraint: the guard is not reentrant within a process (nesting raises `RECOVERY_GUARD_BUSY`); production acquires it once and passes the lease, so this constrains future callers rather than describing a defect. STOP_AND_PRESERVE is behaviourally proven: `rollback_admission` requires all ten mandatory flags true (including `preserve_ledger`), `restore_old_database is False`, zero unresolved effects, and never returns `allow_dispatch=True` — 8/8 fixture assertions passed. The guard path performs no ledger or database IO. Production has no `supervisor.recovery.lock` at all, so there is no legacy empty marker to migrate.

---

## 明确的不主张 / Explicit non-claims

1. 本机 Python/.NET 指纹 PASS **不是**发布器验收，**不是**主机或生产验收。
2. 7877 的 Session-0 结构推断 **不是**注销/重启场景下的实测结论。
3. `PROPOSED_ONLY` 的 ACL 增量 **不是**生效 ACL，**不是**批准。
4. 该候选 **不满足** 既有 `host_remediation` 门禁，**不可**据本证据安装。
5. 本证据 **不构成** 服务安装/启用、身份或 ACL 变更、代理变更、第二 Inventory、手动采集或数据库迁移的授权。

1. Local Python/.NET fingerprint PASS is not publisher acceptance and not host or production acceptance.
2. The Session-0 egress result is a structural inference, not a logoff/reboot measurement.
3. The PROPOSED_ONLY ACL delta is neither an effective ACL nor an approval.
4. The candidate does not satisfy the existing `host_remediation` gates and cannot be installed on this evidence.
5. This evidence authorises no installation/activation, identity or ACL change, proxy change, second Inventory, manual collection or database migration.

## 安全声明 / Safety attestation

未安装服务、未启动服务、未创建目录或账户、未修改 ACL/代理/注册表/计划任务、未注销或重启、未触发 Inventory、未创建第二调度器、未写生产数据库或账本、无 SMTP 或客户邮件。所有夹具仅落在 `C:\Users\15690\AppData\Local\Temp\u1fixture` 与 `…\u1pkg`。

No service installed or started, no directory or account created, no ACL/proxy/registry/scheduled-task change, no logoff or reboot, no Inventory trigger, no second scheduler, no production DB or ledger write, no SMTP or customer email. All fixtures are confined to `C:\Users\15690\AppData\Local\Temp\u1fixture` and `…\u1pkg`.
