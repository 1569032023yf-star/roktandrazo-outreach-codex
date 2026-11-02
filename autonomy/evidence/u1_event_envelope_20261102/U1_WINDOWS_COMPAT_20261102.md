# U1 Windows 兼容验证与部署前检查 / U1 Windows Compatibility Verification and Pre-install Check

**采样时间 / Sample window**: `2026-11-02T17:36:02+08:00` – `2026-11-02T17:38:10+08:00`（`09:36:02Z` – `09:38:10Z`）
**执行身份 / Executing identity**: `RAKTROZO\15690`，SID `S-1-5-21-5926390-557196042-3608508572-1001`，`Elevated=False`
**报告性质 / Nature**: 只读兼容验证与部署前检查。**未安装、未注册服务、未修改 ACL/代理/注册表/计划任务、未触发 Inventory、未写生产数据、无 SMTP。**
**Report-only. No installation, no service registration, no ACL/proxy/registry/scheduled-task mutation, no Inventory trigger, no production data write, no SMTP.**

---

## 零、结论 / Verdicts

| 字段 / Field | 值 / Value |
|---|---|
| `WINDOWS_COMPATIBILITY` | **`BLOCKED_NO_FIXED_CANDIDATE`** |
| `INSTALLATION_ACCEPTED` | `false` |
| `UNATTENDED_ACCEPTED` | `false` |
| `PRODUCTION_ACCEPTED` | `false` |
| `FIXED_CANDIDATE_RECEIVED` | `false` |
| `CANDIDATE_BINDING_FIELDS_SATISFIED` | `1 / 6` |
| `READ_ONLY_CHECKS_COMPLETED` | `6 / 6` |
| `READ_ONLY_CHECKS_FAILED` | `0` |
| `ADMIN_PRIVILEGE_REQUIRED_FOR_NEXT_STEP` | `true` |
| `ONE_TIME_INSTALL_AUTHORITY_REQUIRED` | `true`（且须先满足固定候选前置条件） |

**核心结论：本轮无法执行候选兼容验证，因为 Codex 尚未交付可安装的固定候选包。** 已交付的是可审核源码与离线证据，其自身清单明确写为「非执行、不授权安装」（`allow_install=false`, `release_ready=false`）。

**No fixed installable candidate exists yet.** What was delivered is reviewable source plus offline evidence, self-declared non-executable and non-authorising. Candidate-bound compatibility verification therefore cannot start.

---

## 一、必须继承的历史证据（已逐条核验存在） / Inherited evidence, verified present

| # | 提交 / Commit | 日期 / Date | 核验方式 / Verification | 结果 |
|---|---|---|---|---|
| 1 | `0b09694855e37eb366c10b3b6571282b60b5a19c` | 2026-10-30 14:33 +08 | `git log` 存在于 `workbuddy-task-window` 历史 | **PRESENT** |
| 2 | `54b79153adf8b8d6df1349e5ea78751bf244f24e` | 2026-10-30 15:11 +08 | 同上；Codex 消费回执 `6520177729` 声明的两个 blob SHA 已双向核对一致 | **PRESENT** |
| 3 | `13d061a82568bc147efa689742a61b3e06d95a31` | 2026-11-01 22:53 +08 | `git ls-remote origin refs/heads/main` 实测等于该 SHA，本地 `HEAD` 同值，0/0 | **PRESENT（远端 main HEAD）** |

未重复采集上述三份证据的内容，未重新发起 backend 合同请求。 / No re-collection of the above; no repeated backend-contract request.

### 已接受的 ACL 裁决（不再重开） / Accepted ACL ruling, not reopened

- **Code Root**：保留继承，追加服务 SID `ReadAndExecute`。
- **State Root**：保护 DACL（打断继承），仅 SYSTEM / Administrators `FullControl` + 服务 SID `Modify`。
- **ACL 事务**：持久记录 + 失败补偿。

本轮**未重开该争议**，改为在代码层核验其是否已被真实实现（见 §二.B3，结果 PASS）。

---

## 二、固定候选交付状态（六项绑定字段） / Fixed-candidate status

Codex 最新交付为 Issue 评论 **`6573469646`**（`2026-11-02T09:19:05Z`）：

- 固定源码 / Source commit：`0db17b51d8ce464f1f57dd5ef40d0df266dcf3f8`
- 证据提交 / Evidence commit：`91aa60c6cf52b0c0a9c9e0ff2ddfb5ee39a7f7fc`

| # | 绑定字段 / Binding field | 要求 | 实际 | 判定 |
|---|---|---|---|---|
| 1 | `SOURCE_SHA` | 固定源码 SHA | `0db17b51d8ce464f1f57dd5ef40d0df266dcf3f8` | **SATISFIED** |
| 2 | `PACKAGE_SHA256` | 候选包 SHA256 | **不存在候选包**：`autonomy/evidence/u1_acl_transaction_20261102/` 仅 7 个文本/JSON 文件，仓内该 commit 无任何 `.zip` / 包体；`RELEASE_CHECKLIST.json` 无此字段 | **ABSENT** |
| 3 | `MANIFEST_SHA256` | 包清单 SHA256 | 仅存在安装器**必填参数** `-ApprovedManifestSha256`（`Install-DisabledHost.ps1:5`），**值未提供** | **ABSENT** |
| 4 | 完整文件清单 | 候选包内逐文件清单 | 仅 6 个源码文件清单，非包内文件清单；且新运行时契约要求 6 个 DLL，而唯一曾交付的旧包声明 5 个 → 旧包不可能满足新契约 | **ABSENT** |
| 5 | 安装目标路径 | 已批准的目标路径 | 代码内声明 `C:\Program Files\RoktU1Bridge\v1`、`C:\ProgramData\RoktU1Bridge`；但 `RELEASE_CHECKLIST.json` 全部文件标注 `"production_target": "UNAPPROVED"` | **PARTIAL（UNAPPROVED）** |
| 6 | 安装器版本 | 安装器版本号 | 未声明版本号（仅 `$name='RoktU1Bridge'`、`DisplayName='Rokt U1 Bridge (disabled candidate)'`） | **ABSENT** |

**合计：1 / 6 满足。**

### 代码层硬证据：无候选即无法安装 / Code-level proof

`Install-DisabledHost.ps1` 参数块（第 3–10 行）：

```powershell
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedManifestSha256,
    ...
)
```

`$PackageRoot` 与 `$ApprovedManifestSha256` 均为 **Mandatory**，且后者强制 64 位十六进制。**没有候选包与清单哈希，安装器在参数绑定阶段即失败**，不可能进入任何变更路径。这是「未交付候选」的代码级证明，而非人工判断。

### Codex 自述门禁值 / Producer-declared gate values

取自 `RELEASE_CHECKLIST.json`（`91aa60c6`）：

| 字段 | 值 |
|---|---|
| `schema` | `rokt.u1-acl-offline-release-checklist.v1` |
| `description_zh` | 非执行的离线ACL候选清单，不授权安装。 |
| `release_ready` | `false` |
| `allow_install` | `false` |
| `allow_dispatch` | `false` |
| `allow_cancel_dispatch` | `false` |
| `production_executed` | `false` |
| `scope`（独立审核） | `OFFLINE_ACL_TRANSACTION_ONLY` |

---

## 三、已完成的只读核验（本轮新增，非重复调查） / Read-only checks performed

### B1. 六个源码文件双向 SHA256 核验 — **PASS (6/6)**

方法：经 7877 代理从 `raw.githubusercontent.com` 以 `ref=0db17b51…` 取回原始 blob，分别计算 (a) 原始字节（LF）SHA256 与 (b) 归一化为 CRLF 后的 SHA256，与 `RELEASE_CHECKLIST.json` 的 `git_blob_sha256` / `sha256` 双口径比对。

| 文件 / File | 字节 | LF↔blob 声明 | CRLF↔工作树声明 |
|---|---|---|---|
| `autonomy/windows/Install-DisabledHost.ps1` | 15904 | ✅ | ✅ |
| `autonomy/windows/Acl-Transaction.ps1` | 10261 | ✅ | ✅ |
| `autonomy/disabled_host_package.py` | 6757 | ✅ | ✅ |
| `test_windows_acl_transaction.py` | 14255 | ✅ | ✅ |
| `test_disabled_host_package.py` | 6206 | ✅ | ✅ |
| `test_u1_provision.py` | 4501 | ✅ | ✅ |

**`ALL_SIX_BIDIRECTIONAL_MATCH = true`**。字节数与 GitHub 树记录完全一致。这证明 Codex 的哈希清单内部自洽、交付字节等于声明字节——这是未来安装唯一的 SHA 锚点，故先行独立核验。

> 注：本项只证明「清单与字节一致」，**不构成**对代码正确性、安全性或可安装性的认可。

### B2. 语法与编译检查 — **PASS (6/6)，附带 1 项告警**

- `Install-DisabledHost.ps1`：`[Parser]::ParseFile` → `PARSE_OK=true`，`error_count=0`，2642 tokens。
- `Acl-Transaction.ps1`：`PARSE_OK=true`，`error_count=0`，1804 tokens。
- 4 个 `.py`：`py_compile` 全部 `SYNTAX_OK`（本机 Python 3.13.0）。
- **告警（非阻断）**：`test_windows_acl_transaction.py:270` 触发 `SyntaxWarning: invalid escape sequence '\R'`。位于测试内嵌 PowerShell 字符串，属美观问题，不影响安装器。建议 Codex 改用 here-string 或转义。

### B3. 非对称 ACL 裁决的代码级确认 — **PASS**

直接读取源码确认裁决已被真实实现，而非仅文档承诺：

| 裁决要求 | 代码锚点 | 实现 | 判定 |
|---|---|---|---|
| Code Root **保留继承** | `Acl-Transaction.ps1:129` `if ($codeAcl.AreAccessRulesProtected) { throw 'CODE_INHERITANCE_REQUIRED' }` | **fail-closed 强制**：代码根若为保护 DACL 直接拒绝 | ✅ |
| Code Root 追加服务 SID `ReadAndExecute` | `:130` `AddAccessRule(...'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow')` | 纯追加，不动既有 ACE | ✅ |
| State Root **打断继承** | `:133` `$stateAcl.SetAccessRuleProtection($true,$false)` | 仅状态根执行 | ✅ |
| State Root 仅 3 条 ACE（SYSTEM/Admins Full + 服务 Modify） | `:134` `foreach ($pair in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@($ServiceSid,'Modify')))` | 精确三条 | ✅ |
| 拒绝把服务身份解析为 SYSTEM/Administrators | `:125` `if ($ServiceSid -in @('S-1-5-18','S-1-5-32-544')) { throw 'ACL_SERVICE_IDENTITY_REJECTED' }` | 防身份混淆 | ✅ |
| 持久记录 + 失败补偿 | `:61` `STATE_CREATE_INTENT`（`before='ABSENT'`）、`:146` `APPLY_INTENT` 先持久后变更 | 顺序正确 | ✅ |
| 原子初始 DACL 消除可写继承窗口 | `:46-52` 注释 + `SetAccessRuleProtection($true,$false)` 后建目录 | 已在源码注释与实现中对齐 | ✅ |

**结论：非对称裁决已在代码层真实落地。** 这与上一轮「两处一律打断」的候选脚本形成明确差异，说明 Codex 已按裁决修改。

### B4. 运行时契约实测 — **PASS (6/6)**，含**新增第 6 项**

新版 `Install-DisabledHost.ps1:67-75` 要求运行时 `dependencies.json` 的 `files` **恰好 6 项**（`-ne $runtimePaths.Count` 硬校验），比上轮候选多出 `System.Web.Extensions`。

| 键 / Key | 本机路径 | 存在 | 字节 | SHA256 |
|---|---|---|---|---|
| `clr` | `Microsoft.NET\Framework64\v4.0.30319\clr.dll` | ✅ | 10000696 | `0db5bf856173a818323196fefdd62822c3cddda6f92b2b378f1c6d6ea3b99ead` |
| `mscorlib` | 同上目录 | ✅ | 5445432 | `11ac114c43ecf6996bef58ba3c99fba3693a4560a84eeadde54d193060dc626c` |
| `System` | 同上目录 | ✅ | 3545264 | `2b3c17c6208a0b4b6beb94e1a066f99ba06cdb2ea919479e99d47e8c6d96dc71` |
| `System.Core` | 同上目录 | ✅ | 1551104 | `8b898bed54ae8cc61f9c58cc3eb062724f8357d2bdda338b5d363654ecff333d` |
| `System.ServiceProcess` | 同上目录 | ✅ | 135112 | `39a46cb60718dae105eaa5bd1010ddd7388abb4e4c4699cdf24709f3aae84df3` |
| **`System.Web.Extensions`** | `Microsoft.NET\assembly\GAC_MSIL\System.Web.Extensions\v4.0_4.0.0.0__31bf3856ad364e35\System.Web.Extensions.dll` | ✅ | 1846016 | `5e6378edc06f5a61920aaadb2aba839dd3cf302d6192e08aacd4454ba4cff0b3` |

- 前 5 项哈希与 2026-10-30 记录**完全一致** → 期间无 .NET 补丁漂移。
- 第 6 项 `System.Web.Extensions` 为**本轮新增要求**，本机存在且唯一 GAC 目录为 `v4.0_4.0.0.0__31bf3856ad364e35`，与契约路径字面一致。
- `.NET Framework = 4.8.09221`；契约要求 `framework = '.NET Framework 4 x64'`，`rokt.disabled-host-runtime.v1` schema 由**包内** `runtime/dependencies.json` 提供 → 与包绑定，无法脱离候选单独验证。

> **注意**：唯一曾交付的旧包（`c7f2ac15`）`dependencies.json` 仅 5 项，**不可能通过新契约**。这进一步证明旧包不能替代新候选验收。

### B5. 安装前环境基线 — **PASS（干净）**

| 检查项 | 结果 |
|---|---|
| `C:\Program Files\RoktU1Bridge` | **ABSENT** |
| `C:\Program Files\RoktU1Bridge\v1`（代码根） | **ABSENT** |
| `C:\ProgramData\RoktU1Bridge`（状态根） | **ABSENT** |
| `C:\Program Files` 是否 ReparsePoint | `False` |
| `C:\ProgramData` 是否 ReparsePoint | `False` |
| 两父目录下是否有 `Rokt`/`U1` 相关 Junction/Symlink | **无** |
| 服务 `RoktU1Bridge` | **NOT_REGISTERED** |
| 全机 `*Rokt*` / `*U1*` 服务 | **NONE** |
| C: 卷 | NTFS，200 GB，**FREE 24.2 GB**，`Healthy` |

三点含义：① 无既有内容可被劫持或覆盖，首次安装语义成立；② 无 reparse 预植点，可安全使用 `Assert-NoReparseAncestors` 门禁；③ 容量充裕（较 10-30 的 16.6 GB 反升，无压力）。

### B6. 审计根前置条件 — **BLOCKED（需管理员）**

安装器把 ACL 事务日志固定在 `C:\ProgramData\RoktU1InstallAudit\disabled-host-acl.jsonl`（`:120`），并在变更前调用 `Assert-AclAuditRoot`（`:154`）。该断言（`Acl-Transaction.ps1:21-32`）要求：

1. `AreAccessRulesProtected = true`（必须保护 DACL）
2. `Owner ∈ {S-1-5-18, S-1-5-32-544}`
3. 全部 ACE 仅 SYSTEM / Administrators 且为 `Allow`
4. 恰好 2 条 `FullControl`（CI+OI+无传播）

**实测：`C:\ProgramData\RoktU1InstallAudit` 不存在 → ABSENT。**

源码明确不自动创建审计根（「审计根不自动创建或修补」）。因此在当前非提权身份下，任何 `-Execute` 调用都会在 ACL 事务开始前 `throw`，**属正确的 fail-closed 行为**。

> **这是安装前的真实硬门禁，必须由管理员预先创建并配置该目录。** 属部署前置条件，不是缺陷。

---

## 四、7877 代理：第二次开机样本（证据升级） / Second boot sample

指令要求核查「重启和注销后的实际出口」。本轮获得**第二个独立开机样本**，把上轮 N=1 的推断升级为 N=2 的一致观测。

### 本轮时间线（`2026-11-02`，全部 +08）

| 时刻 | 事件 | 证据来源 |
|---|---|---|
| `09:08:17` | 关机/Restart 发起（`StartMenuExperienceHost.exe`） | System log ID 1074 |
| `09:09:05` | **OS 启动** | Kernel-General ID 12 |
| `09:09:24` | `MyClashHelperService.exe` PID 7732 启动（Session 0） | `Win32_Process.CreationDate`；`StartMode=Auto` / `LocalSystem` |
| `09:11:05` | **Clash GUI `MyClash` PID 29296 启动（Session 1）** | `Get-Process.StartTime` |
| `09:11:06` | **`MyClashCore.exe` PID 29708 启动（Session 0），父进程 = 7732，绑定 `127.0.0.1:7877`** | `Win32_Process` + `Get-NetTCPConnection` |

### 两样本对照 / Two-sample comparison

| 样本 / Sample | 开机 | 服务就绪 | GUI 启动 | 内核启动 | 内核 − 服务 | 内核 − GUI |
|---|---|---|---|---|---|---|
| #1 `2026-10-30` | `08:48:04` | `08:48:23` | `09:20:23` | `09:20:24` | **+32m01s** | **+1s** |
| #2 `2026-11-02` | `09:09:05` | `09:09:24` | `09:11:05` | `09:11:06` | **+1m42s** | **+1s** |

### 判定 / Finding

**关键量：本轮服务在 `09:09:24` 已运行，内核直到 `09:11:06` 才出现——服务空转 102 秒未自行拉起内核。** 两次样本中「内核 − GUI」恒为 `+1` 秒，而「内核 − 服务」在 102 秒与 32 分 01 秒之间大幅变化，说明内核启动时间**只与 GUI 相关，与开机/服务就绪无关**。

补充证据：`09:11:06` 时刻 System 日志**无任何 SCM 事件**（近 7 天与 `MyClash` 相关事件仅 3 条，全部在 10-23 及更早），即内核启动不是服务重启动作。

| 结论项 | 值 |
|---|---|
| `UNATTENDED_PROXY_AVAILABLE` | **`NOT_SUPPORTED_OBSERVED`**（两次开机样本一致；服务空转 102s 未自启内核） |
| `KERNEL_SPAWN_TRIGGER` | `GUI_SESSION_INITIATED`（结构性推断，非唯一因果证明） |
| `KERNEL_SESSION` | `Session 0`（服务托管），但**触发**来自 Session 1 |
| `PROXY_BIND` | 仅回环 `127.0.0.1:7877` |
| `LOGOFF_EGRESS_VERIFIED` | **`UNKNOWN`** —— 未为取证中断当前会话 |
| `REBOOT_EGRESS_VERIFIED` | **`UNKNOWN`** —— 重启后仍需交互登录才会出现内核，无法在不登录情形下观测 |
| `D_VOLUME_DEPENDENCY` | `D:\Clash Plus\MyClashHelperService.exe`（`D:` 未挂载则服务无法启动 → 7877 不监听） |

**操作含义（不变）**：Inventory 以 `SCRAPER_PROXY=7877` 运行，若宿主不把「代理可达」作为启动前置条件，无人登录时 discovery 将全线 `ERR_PROXY_CONNECTION_FAILED`。

### 关于注销测试的立场

`LOGOFF_EGRESS_VERIFIED` 保持 `UNKNOWN` 是**如实**而非回避：真实注销会终止本会话与正在进行的所有取证。**不将交互会话下可用等同于无人值守可用。**

---

## 五、8791 桥接：第二个样本，跨会话持久性再次否定 / Bridge persistence

| 检查项 | 结果 | 证据 |
|---|---|---|
| 8791 监听 | **NOT_LISTENING** | `Get-NetTCPConnection -LocalPort 8791` |
| `pythonw` 进程数 | **0** | `Get-Process -Name pythonw` |
| HKCU Run `RoktDeployChannelSupervisor` | **PRESENT**（指向 `pythonw.exe …\bin\supervisor.py`） | 注册表读取 |
| supervisor 日志末条 | `2026-11-01T22:41:12+08:00` `HEALTH_TRANSITION ok=true`（`bridge_version=2.1`，`test_mode=false`） | `logs/supervisor.jsonl`（16041 B） |
| **今日（`2026-11-02 09:09` 开机）是否有任何日志** | **无** | 日志 `mtime=2026-11-01 22:41:12` |
| `supervisor.lock` | 残留 `pid=43520`, `started_at=2026-11-01T22:40:57+08:00` | `state/supervisor.lock`；该 PID 已不存在（`pythonw` 计数 0）→ **陈旧锁** |

### 判定

| 结论项 | 值 |
|---|---|
| `BRIDGE_CROSS_CALL_PERSISTENCE` | **`FALSE`** |
| `BRIDGE_AUTOSTART_EFFECTIVE` | **`FALSE`**（两次开机样本：`10-30` 与 `11-02`，自启项均存在，两次登录后均 0 个 `pythonw`） |
| `BRIDGE_LOGON_SCOPED` | `TRUE`（`11-01 22:40:57` 启动 → `11-02 09:08` 关机终止，此后无记录） |
| `STALE_LOCK_PRESENT` | `TRUE`（`pid 43520`，已死；因 supervisor 启动时会回收陈旧锁，不构成阻断） |

`8791` 仍**不能**声称具备跨调用持久性或无人登录可用性。

---

## 六、逐项判定（指令第三节四类） / Item verdicts

### 1. 身份和 ACL — **PARTIAL**

| 子项 | 判定 | 依据 |
|---|---|---|
| 实际执行身份 | **PASS** | `RAKTROZO\15690`，SID `…-1001`，`Elevated=False`，Medium IL；`BUILTIN\Administrators` 为仅拒绝组 |
| 服务 SID 是否可用 | **PASS** | 上轮已证 `NT SERVICE\ALL SERVICES`=`S-1-5-80-0`；`NT SERVICE\RoktU1Bridge` 在服务创建前不可解析属正确行为，安装器顺序为先建服务再翻译（`Install-DisabledHost.ps1:177` 前后） |
| Code Root 实际继承 ACL | **UNKNOWN** | 目标目录 `ABSENT`，无法产生「实际」ACL；仅有父目录继承基线与同机先例 |
| State Root 实际有效 ACL | **UNKNOWN** | 同上，`ABSENT` |
| SYSTEM / Administrators / 服务 SID 权限 | **PARTIAL** | 源码设计为 SYSTEM+Admins Full、服务 RX/Modify（见 §二.B3）；**未生效** |
| **审计目录实际存在性、所有者、有效 ACL** | **BLOCKED** | `C:\ProgramData\RoktU1InstallAudit` **ABSENT**；门禁要求保护 DACL + owner∈{SYSTEM,Admins} + 恰 2 条 FullControl；**需管理员创建** |
| 父目录权限 | **PASS（基线）** | `Program Files`/`ProgramData` 均非 ReparsePoint；继承 ACE 已在上轮实证 |
| Reparse Point 风险 | **PASS** | 两父目录非 reparse；无 `Rokt`/`U1` 相关 junction；安装器本身对包路径、代码根、状态根、运行时 DLL、收据均调用 `Assert-NoReparseAncestors` |

**源码设计 ≠ 建议 ACL ≠ 实际生效 ACL**：本轮已明确区分——设计在源码中（PASS 可查），建议已具名（PROPOSED_ONLY），实际生效**均不存在**（目录不存在）。

### 2. 服务兼容性 — **PARTIAL**

| 子项 | 判定 | 依据 |
|---|---|---|
| Windows SCM 服务账户支持 | **PASS** | 本机支持虚拟服务账户（SERVICE SID 命名空间可用）；服务将以 `NT SERVICE\RoktU1Bridge` 运行，无需创建账户、无需存储密码 |
| 服务登录权限（`SeServiceLogonRight`） | **BLOCKED** | `secedit /export /areas USER_RIGHTS` 在非提权令牌下权限不足；虚拟账户由 SCM 授予登录权，属服务创建副作用，**需管理员验证** |
| 服务注册与 Disabled 状态兼容性 | **PARTIAL** | 源码以 `ServiceType=16`（own process）、`StartMode='Disabled'`、`ErrorControl=1` 创建并回读校验（`:177`、`:109-110` 等价逻辑）；**未实际注册** |
| 已有服务升级条件 | **UNKNOWN** | 服务不存在，无升级场景可测 |
| 服务停止状态 | **UNKNOWN** | 未注册，无状态 |
| 服务文件与运行时依赖 | **PASS** | 6/6 DLL 存在且哈希已记录（§二.B4）；`.NET Framework 4.8.09221` 满足 `4 x64` |
| 安装路径 / 磁盘 / 文件权限 | **PASS** | 目标路径全空、C: 24.2 GB 可用、父目录 ACL 已具名 |

### 3. 代理与自动运行 — **FAIL（未达无人值守）**

| 子项 | 判定 |
|---|---|
| 7877 无人登录时可用 | **`NOT_SUPPORTED_OBSERVED`** |
| GUI 与后台内核启动依赖 | 内核 = GUI + 1s（两样本）；服务空转 102s 未自启 |
| Session 0 与交互会话区别 | 内核在 Session 0、触发在 Session 1 |
| 重启/注销后实际出口 | **`UNKNOWN`**（未中断会话取证） |
| 8791 依赖当前登录会话 | **是**（`TRUE`） |
| 8791 跨调用持久性 | **`FALSE`** |
| 8791 注销/重启/无人登录状态 | **不可用**（日志无今日记录） |
| 8791 服务引导与恢复能力 | **无**（仅 HKCU Run，实测两次开机均未触发） |

### 4. 安装和回滚兼容性 — **BLOCKED**

| 子项 | 判定 | 原因 |
|---|---|---|
| 安装包 SHA256 是否一致 | **BLOCKED** | 无候选包，无可比对对象 |
| manifest 是否完整 | **BLOCKED** | 无 `MANIFEST_SHA256` 值（安装器要求必填） |
| 文件是否全部在授权清单中 | **BLOCKED** | 无包内文件清单 |
| 首次安装与升级兼容性 | **BLOCKED** | 同上 |
| 原文件备份与 ABSENT 状态 | **PARTIAL（仅源码可读）** | 源码有 `ABSENT` 语义记录（`STATE_CREATE_INTENT before='ABSENT'`），**未实测** |
| 中断后的恢复能力 | **PARTIAL（仅源码可读）** | 有 `APPLY_INTENT` 先持久后变更 + 逆序补偿 + 恢复准入门禁（`ACL_COMPLETED_INSTALL_RECOVERY_REJECTED`、`ACL_RECOVERY_SERVICE_UNSAFE`），**未实测** |
| 回滚后文件/权限/服务状态 | **BLOCKED** | 无包、无安装，无法回滚 |

---

## 七、未完成原因、权限与授权需求 / Why incomplete, privileges, authority

| 项 | 说明 |
|---|---|
| 未完成原因 | **前置缺失：无可安装的固定候选包。** 六项绑定字段仅 1 项满足；安装器 `-PackageRoot` / `-ApprovedManifestSha256` 均为 Mandatory，无包即在参数阶段失败。 |
| 是否需管理员权限 | **是**，且分两类：<br>① **审计根** `C:\ProgramData\RoktU1InstallAudit` 需管理员创建并配置（保护 DACL + SYSTEM/Admins owner + 恰 2 条 FullControl）→ 当前 `BLOCKED`；<br>② **服务注册**与 `SeServiceLogonRight` 验证需管理员令牌 → 当前 `BLOCKED`；<br>③ 真实**注销/重启**出口验证需中断会话 → 当前 `UNKNOWN`。 |
| 是否需一次性安装授权 | **是**，但**当前不申请**：须先满足「固定候选已交付 + 只读验证通过 + 门禁明确」三项。 |
| 是否已提权或绕过 | **否。** 全程非提权只读；`sc.exe` 被程序黑名单时改直读服务注册表键，未绕过系统限制。 |

---

## 八、给 Codex 的候选交付要求（绑定点清单） / Candidate delivery requirements

新候选必须同时满足，否则我方无法开始验证：

1. `SOURCE_SHA`（已有：`0db17b51…`，若代码再变须更新）
2. `PACKAGE_SHA256` —— 真实 x64 禁用态候选包（`.zip`）的 SHA256
3. `MANIFEST_SHA256` —— 包内 `manifest.json` 的 SHA256，且须等于安装器 `-ApprovedManifestSha256` 传入值
4. **包内完整文件清单**（`path` / `size` / `sha256`），且必须包含 `Install-DisabledHost.ps1:62` 的强制项：
   `service/RoktU1Bridge.exe`、`runtime/dependencies.json`、`config/host.json`、`Install-DisabledHost.ps1`、`Rollback-DisabledHost.ps1`、`Acl-Transaction.ps1`
5. **`runtime/dependencies.json` 必须恰好 6 项**，含新增 `System.Web.Extensions`（路径须为 `Microsoft.NET/assembly/GAC_MSIL/System.Web.Extensions/v4.0_4.0.0.0__31bf3856ad364e35/System.Web.Extensions.dll`），否则 `RUNTIME_CONTRACT_REJECTED`。
   → 本机实测该 DLL 哈希为 `5e6378edc06f5a61920aaadb2aba839dd3cf302d6192e08aacd4454ba4cff0b3`，供对齐。
6. **安装目标路径须由 `UNAPPROVED` 转为 APPROVED**：`C:\Program Files\RoktU1Bridge\v1`、`C:\ProgramData\RoktU1Bridge`、审计根 `C:\ProgramData\RoktU1InstallAudit`。
7. **安装器版本号**（当前未声明）。

附带提醒（非门禁）：`test_windows_acl_transaction.py:270` 的 `invalid escape sequence '\R'` 建议修掉。

---

## 九、最终判定 / Final verdicts

```
FIXED_CANDIDATE_RECEIVED            = false
CANDIDATE_BINDING_FIELDS_SATISFIED  = 1/6
WINDOWS_COMPATIBILITY              = BLOCKED_NO_FIXED_CANDIDATE
INSTALLATION_ACCEPTED              = false
UNATTENDED_ACCEPTED                = false
PRODUCTION_ACCEPTED                = false
```

| 子结论 | 值 |
|---|---|
| `SOURCE_AND_EVIDENCE_SHA_VERIFIED` | **true**（6/6 双向一致） |
| `ACL_RULING_IMPLEMENTED_IN_CODE` | **true** |
| `RUNTIME_CONTRACT_SATISFIED_ON_HOST` | **true**（6/6 DLL） |
| `PREINSTALL_ENV_CLEAN` | **true**（目标空、无 reparse、无服务、容量足） |
| `AUDIT_ROOT_PRECONDITION` | **BLOCKED_ADMIN_REQUIRED** |
| `PROXY_UNATTENDED` | **NOT_SUPPORTED_OBSERVED**（N=2） |
| `PROXY_LOGOFF_EGRESS` | **UNKNOWN** |
| `BRIDGE_CROSS_CALL_PERSISTENCE` | **false**（N=2） |
| `BRIDGE_AUTOSTART_EFFECTIVE` | **false** |

`CURRENT_SAFE=UNKNOWN`；`BUSINESS_GROWTH_VERIFIED=UNKNOWN`（本报告不涉及业务指标）。

---

## 十、安全声明 / Safety attestation

未安装或注册服务；未创建 `C:\Program Files\RoktU1Bridge*`、`C:\ProgramData\RoktU1Bridge`、`C:\ProgramData\RoktU1InstallAudit`；未创建账户；未修改任何 ACL；未修改代理（`SCRAPER_PROXY` 仍 `7877`，未动 `BD_MX_HTTPS_PROXY`）；未修改注册表或计划任务；未注销或重启；未触发 Inventory；未创建第二调度器；未写生产数据库或账本；无 SMTP、无客户邮件。

所有下载与计算仅落于 `%TEMP%\u1src` 与 `%TEMP%` 下临时 JSON；未在系统路径或生产项目目录写入任何内容。

No service installed or registered; no directory, account or ACL created or modified; no proxy, registry or scheduled-task change; no logoff or reboot; no Inventory trigger; no second scheduler; no production DB/ledger write; no SMTP.
