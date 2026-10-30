# Windows 环境正式证据 / Formal Windows Environment Evidence

- **采样时间 / Sampled at**: `2026-10-30T15:10:15+08:00` (`2026-10-30T07:10:15Z`)
- **证据类别 / Evidence class**: `READ_ONLY_LOCAL_OBSERVATION`
- **是否构成批准 / Is this an approval**: **否 / NO** — 观测不等于批准 / observations are not approvals
- **机器可读版 / Machine-readable**: `WINDOWS_ENVIRONMENT_EVIDENCE_20261030.json`
- **绑定候选 / Bound candidate**: `SOURCE_SHA=d7d424c120281981e70753ea1c15fe130134929f`, `EVIDENCE_PACKAGE_SHA=c7f2ac15391f3fe3522d3e218650749474b39188`

---

## 0. 结论摘要 / Summary

| # | 项目 / Item | 上轮 / Previous | 本轮 / Now | 变化 / Delta |
|---|---|---|---|---|
| 1 | Windows 身份与 ACL / Identity and ACL | PARTIAL | **PARTIAL** | 生效 ACL 由「推断」升级为「先例实证」/ effective ACL upgraded from inference to empirical precedent |
| 2 | 7877 非交互出口 / 7877 non-interactive egress | PARTIAL（结构支持） | **NOT_SUPPORTED_OBSERVED** | **降级 / downgraded** — 内核由 GUI 触发启动 / kernel is GUI-triggered |
| 3 | 运行时与发布器 / Runtime and publisher | PARTIAL | **PARTIAL** | 无变化，仍是架构缺口 / unchanged architectural gap |
| 4 | Inventory 唯一执行权与锁 / Sole authority and lock | PASS | **PASS** | 复验通过 / re-verified |
| 5 | v2 guard 双向迁移 / Bidirectional migration | PASS | **PASS** | 无变化 / unchanged |

**整体 / Overall: 2 PASS / 3 PARTIAL / 0 BLOCKED.**
但第 2 项从「未证实」变成「有反证」/ item 2 moved from "unproven" to "counter-evidenced".

---

## 1. 主机事实 / Host facts

| 项 / Item | 值 / Value |
|---|---|
| 计算机名 / Computer name | `RAKTROZO`（`WORKGROUP`，未加域 / not domain-joined） |
| 机型 / Model | HP ZHAN 99 Pro 23.8 inch G9 All-in-One |
| CPU / RAM | i7-12700（12C/20T）/ 15.7 GB |
| 操作系统 / OS | **Microsoft Windows 11 家庭版 中文版**，Build **26200**，64-bit |
| 安装日期 / Installed | 2026-06-02 |
| 最近启动 / Last boot | `2026-10-30T08:48:03+08:00`（前次关机 Event 6006 @ 08:47:33） |
| 快速启动 / Fast Startup | `HiberbootEnabled=1`（混合启动 / hybrid boot） |
| .NET Framework | **4.8.09221**；无 .NET Core / `C:\Program Files\dotnet` 不存在 |
| 磁盘 / Disks | C: 200 GB（剩 **16 GB**）；D: 275.7 GB（剩 167 GB，NVMe，GPT，Online） |

**家庭版带来的真实约束 / What Home edition actually constrains:**

1. 无 `secpol.msc` / `gpedit.msc`，用户权利只能通过**提权**的 `secedit` 或 LSA API 读写。
2. BitLocker 无管理界面，`Get-BitLockerVolume` 对非提权会话返回拒绝访问。
3. **服务、虚拟服务账户 `NT SERVICE\<name>`、SCM 全部正常可用** —— 装服务本身不受家庭版限制。

---

## 2. 执行身份与权限 / Identity and privileges

| 项 / Item | 值 / Value |
|---|---|
| 身份 / Identity | `RAKTROZO\15690` |
| SID | `S-1-5-21-5926390-557196042-3608508572-1001` |
| 完整性级别 / Integrity | **Medium**（`S-1-16-8192`），**未提权** |
| Administrators | `S-1-5-32-544`，状态 = **「只用于拒绝的组」deny-only** |
| UAC | `EnableLUA=1`，`ConsentPromptBehaviorAdmin=5`，`PromptOnSecureDesktop=1`，`FilterAdministratorToken=1` |
| 令牌特权 / Privileges | 仅 5 项，**无 `SeDebugPrivilege` / `SeTakeOwnershipPrivilege` / `SeBackupPrivilege`** |

**含义 / Implication**：本会话没有任何静默提权路径，安装必须走一次 UAC 同意提示。

### 2.1 虚拟账户能力 / Virtual account capability

| 探测 / Probe | 结果 / Result |
|---|---|
| `NT SERVICE\TrustedInstaller` | **RESOLVED** → `S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464` |
| `NT SERVICE\ALL SERVICES` | **RESOLVED** → `S-1-5-80-0` |
| `NT SERVICE\RoktU1Bridge` | `UNRESOLVABLE_UNTIL_SERVICE_CREATED`（预期 / expected） |

命名空间可用。`RoktU1Bridge` 解析失败仅因服务尚不存在，安装脚本「先建服务、再翻译账户」的顺序正确。**未创建任何账户。**

### 2.2 `SeServiceLogonRight` — BLOCKED

```
secedit /export /areas USER_RIGHTS /cfg <tmp>.inf
exit_code = 740  →  “你没有执行该命令的足够权限”
file_created = False
```

- 非提权无法读取。**这不是部署阻塞**（安装器本身必须提权），只是我们无法在安装前预先证明。
- 装完后应在提权 shell 复核：服务能从 `Stopped` 进 `Running` 且系统日志出现 7036，即证明登录权已具备。

---

## 3. 生效 ACL 与最小增量 / Effective ACL and minimal deltas

方法：`Get-Acl`（仅 DACL）+ `icacls` 读**已存在的同类目录**作为先例。**未创建目录、未修改任何 ACL。**

### 3.1 父目录 / Parents

| 路径 | Owner | 保护继承 | ACE 总数 | 可继承 |
|---|---|---|---|---|
| `C:\Program Files` | `NT SERVICE\TrustedInstaller` | `True` | 13 | **7** |
| `C:\ProgramData` | `NT AUTHORITY\SYSTEM` | `True` | 5 | **5** |

### 3.2 先例实证 / Empirical precedent（关键）

`C:\Program Files\AMD` —— **13 条全部继承、0 条显式**，`icacls` 实测：

```
NT SERVICE\TrustedInstaller:(I)(F)
NT AUTHORITY\SYSTEM:(I)(F)
BUILTIN\Administrators:(I)(F)
BUILTIN\Users:(I)(RX)                      ← 对子目录本身生效
BUILTIN\Users:(I)(OI)(CI)(IO)(GR,GE)       ← 对更深层生效
CREATOR OWNER:(I)(OI)(CI)(IO)(F)
```

同样的「13 继承 / 0 显式」模式在 8 个目录上复现：`Billfish`、`Google`、`HP`、`HPCommRecovery`、`Intel`、`Microsoft Office`、`Microsoft Office 15`、`Microsoft OfficePLUS`。

`C:\ProgramData\CooCare` —— **5 条全部继承、0 条显式**：

```
NT AUTHORITY\SYSTEM:(I)(OI)(CI)(F)
BUILTIN\Administrators:(I)(OI)(CI)(F)
CREATOR OWNER:(I)(OI)(CI)(IO)(F)
BUILTIN\Users:(I)(OI)(CI)(RX)
BUILTIN\Users:(I)(CI)(WD,AD,WEA,WA)        ← 任何本机用户都能建子目录
```

### 3.3 新建目录的预期生效 ACL / Predicted effective ACL

| 目标 / Target | 预期生效 ACE / Predicted effective |
|---|---|
| `C:\Program Files\RoktU1Bridge` | SYSTEM(F)、Administrators(F)、Users(RX)、CREATOR OWNER(仅继承 F)。**没有任何 ACE 授予服务 SID** |
| `C:\ProgramData\RoktU1Bridge` | SYSTEM(F)、Administrators(F)、CREATOR OWNER(仅继承 F)、Users(RX)、**Users 可建子目录** |

置信度：高 —— 12 个 Program Files 子目录中 8 个完全一致，ProgramData 抽样全部一致。

### 3.4 最小增量提案 / Minimal deltas —— `PROPOSED_ONLY`（未应用、未批准）

- code root：授予 `NT SERVICE\RoktU1Bridge` **ReadAndExecute**（保持继承，不打断）。
- state root：授予 `NT SERVICE\RoktU1Bridge` **Modify**。
- 建议**移除** state root 上继承来的 `BUILTIN\Users (CI)(WD,AD,WEA,WA)`，阻断任意本机用户在该目录下建子目录。

**不能靠 `Everyone` 或继承兜底**：两个父目录 ACL 中既无 `Everyone`，也无服务 SID。
**`NT SERVICE\RoktU1Bridge` 是否属于 `BUILTIN\Users` = UNKNOWN**（无法为不存在的服务 SID 枚举成员，且禁止建账户）→ 因此**必须显式 ACE**。

---

## 4. 7877 非交互出口 —— 本轮最重要的反转 / The most important reversal

**判定 / Verdict: `NOT_SUPPORTED_OBSERVED`**（上轮为「结构性支持，未实测」，本轮找到反证。）

### 4.1 时间线 / Timeline（2026-10-30，+08）

| 时刻 | 事件 |
|---|---|
| 08:47:33 | Event 6006 上一会话干净关机 |
| 08:48:03 | 冷启动（LastBootUpTime） |
| 08:48:20 | Event 6005 / 6013 事件日志服务启动 |
| 08:48:23 | 交互登录（LogonSession Type 2）；**MyClashHelperService PID 6356 启动** |
| 08:48:25 | `explorer.exe` 在 Session 1 启动 |
| **09:20:23** | **`MyClash.exe` GUI 启动（Session 1）**，同时写入 `%APPDATA%\Clash Plus\Clash Plus\Cloak.lock` |
| **09:20:24** | **`MyClashCore.exe` PID 15344 启动**，父进程 = 6356 服务，Session 0，绑定 `127.0.0.1:7877` |

### 4.2 为什么这是反证 / Why this is counter-evidence

1. 内核启动比开机晚 **31 分 21 秒**，比 GUI 只晚 **1.2 秒** —— 唯一自洽的因果链是 GUI → 服务 → 内核。
2. **09:20 没有任何 SCM 事件**，所以它不是服务重启（只有 2026-09-30 与 2026-10-23 两次 7045 安装事件、2026-10-23 一次 7034 意外停止）。
3. 近 7 天 **Application 日志中没有 `MyClashCore.exe` 崩溃记录**，排除「开机起过、后来崩了」。
4. 该服务**没有任何故障恢复动作**（`FailureActions` 不存在），内核若静默死掉，SCM 永远不会重启它。

### 4.3 仍然 UNKNOWN / Still unknown

- 服务能否在**没有任何 GUI 请求**的情况下按需拉起内核（只有一次开机样本）。
- 真实注销后行为（未测，测了会中断本会话）。
- Fast Startup 混合启动恢复后的行为（`HiberbootEnabled=1`）。
- D: 的 BitLocker 状态（非提权被拒）。

### 4.4 对服务设计的硬约束 / Hard constraint for the service design

Inventory 通过 `SCRAPER_PROXY=http://127.0.0.1:7877` 走 Playwright。**如果 7877 只在交互式 GUI 会话期间存在，无人登录时服务启动即无出口，discovery 会以 `ERR_PROXY_CONNECTION_FAILED` 全线失败。**

因此服务必须**以代理可达为前提门控**，或者明确接受「仅在控制台会话存在时运行」。这一条比 ACL 更早决定成败。

### 4.5 当前出口实测 / Egress verified right now

`gstatic` → **204**，`api.github.com` → **200**，回环 `127.0.0.1:52163 → 7877` 连接正常。系统代理 `ProxyEnable=1`、`ProxyServer=127.0.0.1:7877`、`ProxyOverride` 长度 482 —— **未被改动**。

另注：本 Agent 会话还带 `HTTP_PROXY=127.0.0.1:63440`（宿主托管），与生产 `SCRAPER_PROXY=7877` 是两条不同出口，**Session 0 服务两者都不继承**。

---

## 5. 服务与自启矩阵 / Services and autostart

| 服务 | 状态 | 启动 | 账户 | 结论 |
|---|---|---|---|---|
| `MyClashHelperService` | Running | **Auto** | LocalSystem | **无故障恢复动作**，崩溃不重启 |
| `BDExecutionHost` | Stopped | Manual | LocalSystem | **僵尸服务** —— `pythonservice.exe` 磁盘上不存在 |
| `BDESVC`（BitLocker） | Running | Manual | LocalSystem | 存在但管理 API 仍需提权 |

**计划任务 / Scheduled tasks** —— 全部 `Interactive` + `Limited` + 用户 `15690`：

| 任务 | 状态 | 最近运行 | 结果 |
|---|---|---|---|
| `RoktRazo-BD-Outreach` | **Disabled** | 2026-09-22 23:00 | 0 |
| `RoktRazo-BD-PreSend` | **Disabled** | 2026-09-08 22:30 | 0 |
| `RoktRazo-BD-PostSend` | Ready | 2026-10-30 00:10 | 0 |

**这意味着**：即使解决了服务层，这 3 个任务在无人登录时也不会执行 —— 它们的 `LogonType` 是交互式。

### 5.1 桥接自启实证失败 / Bridge autostart is registered but not effective

| 项 | 值 |
|---|---|
| HKCU Run | `RoktDeployChannelSupervisor` = `pythonw.exe supervisor.py`（**存在**） |
| 目标文件 | `pythonw.exe` 90112 B **存在**；`supervisor.py` 13578 B **存在** |
| 当前进程 | **0 个 `pythonw`** |
| 日志最后活动 | `2026-10-29T22:41:04+08:00`；heartbeat mtime `22:54:51` |
| 8791 监听 | **无** |
| 残留锁 | `state\supervisor.lock` 64 B，owner pid 24692 **已消失** |

日志显示 10-29 22:40:50 `STALE_LOCK_RECLAIMED` → `SUPERVISOR_START pid=40556` → `SPAWN child_pid=36628` → 22:41:04 `HEALTH_TRANSITION ok=true`，**随后没有任何 shutdown 或崩溃记录就消失了**。今天 08:48 登录后也没有被 Run 键拉起。

**结论**：`BRIDGE_AUTOSTART_EFFECTIVE = FALSE`。

---

## 6. 运行时指纹 / Runtime fingerprints

| 项 | 值 |
|---|---|
| Python | **3.13.0**，`C:\Users\15690\AppData\Local\Programs\Python\Python313\python.exe` |
| python.exe SHA256 | `62ebc90a2884bb63a0cd67e789cafdd51e771eee043587e2354327b4ccc9bb05` |
| SQLite | **3.45.3**，`_sqlite3.pyd` SHA256 前 32 位 `3e625978d7c55f4b609086a872177c42` |
| 时区 | `+0800`（Asia/Shanghai） |
| 架构 | AMD64 |
| .NET Framework 4 x64 | 5/5 DLL 存在（System / System.Core / System.ServiceProcess / mscorlib / clr） |

**两个必须在服务里显式注入的环境事实：**

1. managed python（`.workbuddy\binaries\...3.13.12`）缺 `requests` / `bs4` / `playwright` / `dnspython`，**只能跑纯 stdlib 的 supervisor，不能跑 Inventory**。
2. `PLAYWRIGHT_BROWSERS_PATH` 未设置。LocalSystem 服务找不到用户目录下的 chromium → 必须显式注入，否则 discovery 启动即失败。

---

## 7. 发布器能力回顾（不变）/ Publisher capability (unchanged)

`SEAL_VERIFIED_FULL`。四项能力只有**原子替换**支持：

| 能力 | 支持 |
|---|---|
| 原子替换 | **SUPPORTED**（同卷临时文件 + fsync + 复制 DACL + `os.replace`） |
| 新建文件 | **NOT_SUPPORTED**（`target_absent` → `deployable=false`） |
| 目标原本不存在的备份表示 | **NOT_SUPPORTED**（无缺席哨兵） |
| 删除回滚 | **NOT_SUPPORTED**（只还原 `.before.bak`） |
| 白名单 | `extensions=[".py"]`，显式拒绝 `*.json`，13 个精确路径，≤6 文件 / 256 KiB |

候选 7 个文件是 `.json/.cs/.exe/.ps1`，**0 个 `.py`** → 通道在架构层面无法承载。这是表达能力缺口，不是门禁失败。

---

## 8. 未做与不主张 / Not done, not claimed

**未做：** 未安装/启动/停止任何服务；未创建目录或账户；未修改 ACL / 代理 / 注册表 / 计划任务；未注销或重启；未触发 Inventory；未创建第二调度器；未写生产数据库或账本；未触碰生产 guard 账本。

**不主张：**

- 本机 Python/.NET 指纹 PASS ≠ 发布器验收 ≠ 主机或生产验收。
- Session-0 代理结论基于**一次开机样本**，**不是**注销/重启实测。
- `PROPOSED_ONLY` 的 ACL 增量不是生效 ACL，更不是批准。
- 该候选**仍不满足**既有 `host_remediation` 门禁，**不可**据本证据安装。

`CURRENT_SAFE=UNKNOWN`；`BUSINESS_GROWTH_VERIFIED=UNKNOWN`.

---

## 9. 工具限制（如实记录）/ Tooling limitations

| 限制 | 影响 | 替代 |
|---|---|---|
| `sc.exe` 被宿主程序黑名单阻断（不可绕过，未重试） | 无法用 `sc qc/qfailure/qsidtype` | 直读服务注册表键 |
| `Add-Type`（P/Invoke）被策略阻断 | 无法调用 LSA 用户权利 API / `IsProcessInJob` | 如实标 BLOCKED |
| `quser.exe` 在家庭版不存在 | 无法用 quser 取登录时间 | `Win32_LogonSession` |
| `secedit` / BitLocker 需提权 | exit 740 / 拒绝访问 | 标 BLOCKED，给出装后复核步骤 |
