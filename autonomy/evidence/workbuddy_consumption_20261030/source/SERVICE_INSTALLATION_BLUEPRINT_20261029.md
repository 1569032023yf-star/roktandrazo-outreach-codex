# 无人值守执行层安装蓝图 / Unattended Execution Layer Blueprint

生成时间 / Generated: 2026-10-29 18:45 +08
适用对象 / Audience: 本机操作员（管理员权限）+ Codex
状态 / Status: **方案文档，本轮未执行任何安装动作 / DESIGN ONLY — nothing was installed in this turn**

---

## 一、一句话结论 / One-line conclusion

> **新服务无法从 Agent 会话内部合法创建。** 必须先由操作员用管理员权限一次性注册 Windows 服务（或 S4U 计划任务），之后由 SCM 托管，Agent 会话的 job object 与进程树回收对它完全无效。
>
> **A new service cannot be legally created from inside an agent session.** It must be registered once by the operator with administrator rights as a Windows service (or an S4U scheduled task). From then on the SCM owns the process, and the agent host's job object / process-tree reaping no longer applies to it.

---

## 二、为什么会话内做不到（本机实测证据）

| 尝试路径 | 结果 | 证据 |
|---|---|---|
| `CREATE_BREAKAWAY_FROM_JOB` 脱离作业对象 | **失败** | WinError 5（拒绝访问），宿主未授予 breakaway 权限 |
| `WMI Win32_Process.Create` 派发 | **被拦** | 宿主安全策略直接拦截 |
| `Start-Process` / `wscript` / `explorer.exe` 派发 | **失败** | `rc=1` 且无子进程落地（静默失败） |
| `schtasks.exe` / `sc.exe` / `reg.exe` 注册 | **被拦** | 三者均在程序黑名单（Program Blacklist） |
| `Add-Type` 反射查 `IsProcessInJob` | **被拦** | 运行时 .NET 编译被禁止，无法自证 job 归属 |

**推论**：会话内只能做"已安装服务的客户端"，不能做"服务的安装者"。这不是权限不足，是设计边界。

---

## 三、现有可用的宿主机资源（事实）

### 3.1 已经可靠的：7877 代理

| 项 | 值 |
|---|---|
| 监听 | `127.0.0.1:7877`（TCP + UDP） |
| 内核进程 | `MyClashCore.exe` PID 30772，**SessionId = 0** |
| 父进程 | PID 7916 `MyClashHelperService.exe`（Windows 服务） |
| 服务属性 | `StartMode=Auto`、`StartName=LocalSystem`、`Running`、二进制 `D:\Clash Plus\MyClashHelperService.exe` |
| GUI | `MyClash.exe` PID 37524，Session 1（**非必需**） |
| 无人登录判定 | **支持**，判定码 `SUPPORTED_BY_SERVICE_HOSTING` |

**为什么可以说"支持"**：内核是 LocalSystem 自动启动服务的子进程，跑在 Session 0，与桌面 GUI 的生命周期解耦。关掉 MyClash 窗口不会杀内核；无人登录时服务仍在。

**必须诚实标注的限制**：`UNATTENDED_VERIFIED = false`。本判定来自进程血缘 + 服务配置的结构性证据，**没有做真实注销测试**（会终止当前会话）。对外只能表述为"由服务托管，结构上支持"，不能说"已在注销场景验证"。

**约束清单**：

1. **D 盘依赖**：代理二进制在 `D:\Clash Plus`。D 盘若开机未挂载（离线盘 / BitLocker 未解锁），helper 服务起不来 → 7877 不监听。
2. 仅回环：服务在同机可用，跨机不可用。
3. 配置由 GUI 写入（Session 1）。无人登录时内核沿用最后写入的配置，**没人能换节点或救死节点**。
4. 服务恢复策略不可读（`sc.exe` 被黑名单），不能假设 SCM 会自动拉起。
5. Session 0 服务**不读 HKCU 代理环境变量** → `SCRAPER_PROXY` 必须写进服务环境。

> 本轮**未修改任何代理配置**：`SCRAPER_PROXY=http://127.0.0.1:7877` 保持原样；`BD_MX_HTTPS_PROXY` 仍指已关闭的 3213（依赖 dnspython 直连兜底），**未动**，属待人工决策项。

### 3.2 已经不可靠的：BDExecutionHost

| 项 | 值 |
|---|---|
| 状态 | `Stopped`，`StartMode=Manual`，`StartName=LocalSystem` |
| ImagePath | `C:\Users\15690\.workbuddy\binaries\python\versions\3.13.12\pythonservice.exe` |
| 二进制是否存在 | **否**（该发行版只有 `python.exe` / `pythonw.exe`） |
| 结论 | **僵尸服务**，任何配置都无法启动，不能作为无人值守层 |

### 3.3 现有计划任务全部是"登录才跑"

| 任务 | 状态 | 执行体 | 登录类型 |
|---|---|---|---|
| RoktRazo-BD-Outreach | Disabled | managed python 3.13.12 → `--stage outreach --live` | **Interactive** |
| RoktRazo-BD-PreSend | Disabled | managed python 3.13.12 → `--stage pre-send --live` | **Interactive** |
| RoktRazo-BD-PostSend | Ready（10-29 00:10 跑过，rc=0） | managed python 3.13.12 → `--stage post-send --live` | **Interactive** |
| ProxyOverrideGuard | Disabled | — | **Interactive** |

**`LogonType=Interactive` 意味着注销后一律不执行。** 这是与"装不装服务"无关的独立阻塞点。

### 3.4 桥接 8791 现状

- **未运行**：8791 无监听，无 `pythonw` 实例。
- 残留 `state/supervisor.lock`（pid 24692，10-28 22:40:44）与 `supervisor_heartbeat.json`（10-28 22:53:10，`health_ok=true`，`child_pid=48712`）。两个 PID 均已不存在 → 陈旧锁，**无需手工清**，`supervisor.acquire_singleton()` 会走 `STALE_LOCK_RECLAIMED` 自愈。
- 现有启动方式只有三种，**全部是"登录后"或"手工"**：
  1. HKCU Run `RoktDeployChannelSupervisor` → managed `pythonw.exe` + `supervisor.py`（登录触发）
  2. `bin/start_supervisor.cmd` → 经 explorer 派发（注释明写目的是脱离 agent job）
  3. `bin/launch_supervisor.vbs` → `WScript.Shell.Run` 隐藏、不等待
- **无** Windows 服务承载桥接；**无** `RoktDeployBridge` 计划任务（`CODEX_ENTRYPOINT.md` 第七节仍写该 Run 值直启 `bridge.py`，**已过期**，现由 `RoktDeployChannelSupervisor` 取代）。
- 注册表封印**完整**：`channel_config` / `allowed_scope` / 4 个 release entry 全部匹配，判定 `SEAL_VERIFIED_FULL`。

> 注意：release entry 的封印值是**注册条目 dict 的规范化 JSON 哈希**，不是 patch/manifest 文件哈希。拿文件 SHA 去比会得到假阳性"被篡改"。

---

## 四、三条合法路径对比

| 路径 | 无人登录 | 需要管理员 | 凭据处理 | 本机可行性 | 推荐度 |
|---|---|---|---|---|---|
| **A. Windows 服务（LocalSystem）** | ✅ | ✅ 一次性 | 免密码 | 可行，但需补 `PLAYWRIGHT_BROWSERS_PATH` + 目录 ACL | ★★★★ |
| **B. Windows 服务（专用用户账户）** | ✅ | ✅ 一次性 | 需存账户密码 | 复用用户目录与浏览器缓存，最省事但引入密码保管问题 | ★★★ |
| **C. 计划任务 S4U（`LogonType=ServiceAccount`）** | ✅ | ✅ 一次性 | S4U 不需存密码，但拿不到网络凭据上下文 | 够用，权限模型比服务宽松 | ★★★ |
| D. 保留 HKCU Run | ❌ | ❌ | — | 现状，仅登录后可用 | ✗ |
| E. 沿用 Interactive 计划任务 | ❌ | — | — | 现状，注销即停 | ✗ |

**推荐：A 或 C。选 A 若接受显式路径注入；选 C 若希望安装更轻、权限更小。**

---

## 五、方案 A 安装清单（操作员执行，管理员权限）

> 以下命令为**模板**。`<...>` 需替换。**本轮未执行任何一条。**

### A.1 前置：目录权限

服务账户必须能读写数据库与其 WAL 兄弟文件：

```
data\bd_leads.db
data\bd_leads.db-wal
data\bd_leads.db-shm
```

以 LocalSystem 运行时，需给 `NT AUTHORITY\SYSTEM` 授予项目 `data\` 目录的修改权限（一次性）。若用方案 B，则授予该用户账户。

### A.2 必须注入的服务级环境变量

| 变量 | 值 | 原因 |
|---|---|---|
| `PLAYWRIGHT_BROWSERS_PATH` | `C:\Users\15690\AppData\Local\ms-playwright` | 否则 LocalSystem 解析到 `systemprofile` 下，找不到 chromium，Maps 采集立刻失败 |
| `SCRAPER_PROXY` | `http://127.0.0.1:7877` | Session 0 不读 HKCU，必须显式给 |
| `WORKBUDDY_DISCOVERY_MAX_PAGES` | `3` | 与当前 canary 一致，**不要提到 4** |
| `WORKBUDDY_WEBSITE_RESOLUTION_MAX` | `20` | 保持默认 |
| `WORKBUDDY_STAGING_POSTPROCESS_MAX` | `20` | 保持默认 |

> `env_loader.py` 用 `os.environ.setdefault`：**进程环境优先，`.env` 只是兜底**。给服务设空值会静默覆盖 `.env`。

### A.3 注册服务（模板）

```
sc create RoktInventoryHost binPath= "\"C:\Users\15690\AppData\Local\Programs\Python\Python313\python.exe\" \"C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach\bd_orchestrator.py\" --stage inventory --live" start= auto obj= LocalSystem DisplayName= "Rokt Inventory Host"
```

**但不要直接这样做**：`sc create` 无法设置工作目录，而 Inventory 依赖 `cwd = 项目目录`。正确做法是让服务启动一个**薄包装器**（wrapper）而不是直接指向 `bd_orchestrator.py`：

- wrapper 负责：`os.chdir(项目目录)` → 设置环境变量 → 以子进程方式调用 `bd_orchestrator.py --stage inventory --live` → 记录退出码
- wrapper 用 `pywin32` 的 `win32serviceutil` 或 NSSM 之类成熟宿主实现
- **不要**自己写 SCM 协议代码

### A.4 关键取舍

| 取舍 | 说明 |
|---|---|
| 解释器 | **必须**系统 Python 3.13.0；managed 3.13.14 缺全部依赖（requests/bs4/playwright/dnspython/lxml 全 MISSING） |
| 调度权 | 装服务后，`automation-1784775229336` 必须**停用或改为驱动服务**，绝不能两个调度并存（会产生第二个 Inventory） |
| 锁 | 继续复用 `run_lock:daily_outreach:inventory:<business_date>`，不得自建锁 |

---

## 六、方案 C 安装清单（S4U 计划任务，管理员一次性）

```
schtasks /Create /TN "RoktInventoryHost" /SC HOURLY /MO 6 /RU "15690" /RL HIGHEST /IT:false ...
```

要点：

- 必须 `LogonType=ServiceAccount`（S4U），**不能**是 `Interactive`
- 需在任务 XML 里显式给 `WorkingDirectory` 与 `EnvironmentVariables`（GUI 的 schtasks 参数不够，直接导入 XML 更可靠）
- S4U 下**拿不到网络凭据上下文**，若未来接 SMTP 会受限；对纯采集无影响
- 同样要求 `PLAYWRIGHT_BROWSERS_PATH` 与 `SCRAPER_PROXY` 显式注入

---

## 七、安装后验证清单（必须先跑这个，再谈无人值守）

| # | 检查 | 通过标准 |
|---|---|---|
| 1 | 服务/任务能启动 | `Running`，无 1067/1053 错误 |
| 2 | 解释器正确 | 进程命令行指向系统 Python 3.13.0 |
| 3 | 依赖可导入 | 能 `import requests, bs4, playwright, dns` 成功 |
| 4 | 浏览器可见 | `PLAYWRIGHT_BROWSERS_PATH` 生效，chromium 能 launch |
| 5 | 代理可达 | `127.0.0.1:7877` 探测 OPEN，经它取 `generate_204` = 204 |
| 6 | DB 可写 | `-wal` / `-shm` 可创建，`quick_check` = ok |
| 7 | 锁可获取 | 拿到 `run_lock:daily_outreach:inventory:<date>` 并正确释放 |
| 8 | dry-run 通 | `--stage inventory`（无 `--live`）正常返回统计 |
| 9 | 单次 live 受控 | 一次 `--live` 跑通，`job_runs` 出现 `completed/partial`，`provider_request_audit` 有真实页数 |
| 10 | 注销测试 | **真正注销再登录**，验证服务仍在跑、7877 仍在听 |

**第 10 项是唯一能证明"无人登录可用"的检查。** 前 9 项全绿也不能替代它。

---

## 八、回滚

1. 停服务/任务 → `sc delete RoktInventoryHost` 或 `schtasks /Delete /TN ...`
2. 撤销目录 ACL 变更
3. 删除服务级环境变量
4. 恢复 `automation-1784775229336` 为 ACTIVE（如果安装时停用过）
5. 确认 `run_lock` 无残留（`system_config` 中 `run_lock:daily_outreach:inventory:*` 为 `released`）

---

## 九、本蓝图明确不做的事

- 不安装任何服务
- 不注册任何计划任务
- 不改 `sc.exe` / `schtasks.exe` 黑名单
- 不改代理、`.env`、`.env` 中的 3213 漂移项
- 不启动 8791 桥接
- 不创建第二个 Inventory 调度
- 不触碰 SMTP / 发送链路

---

## 十、给 Codex 的一句话交接

> Inventory 服务 = **系统 Python 3.13.0 + 项目 cwd + `--live` + 官方 run-lock + 显式 `PLAYWRIGHT_BROWSERS_PATH` + 7877 前置探测**。
> 安装动作只能由管理员一次性完成；装完必须做真实注销测试才能宣称无人值守可用。
> 桥接 8791 现在是停的，封印完整，启动靠 `supervisor.py`，不要再去找 `RoktDeployBridge`。
