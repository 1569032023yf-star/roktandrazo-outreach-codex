# Phase 1 服务化就绪评估 / Service Readiness Assessment

生成 / Generated: 2026-10-29 18:48 +08
产出者 / Producer: workbuddy-production-operator
性质 / Nature: **只读审计 + 契约编制**（未安装服务、未启桥接、未改代理、未写生产库）
Nature: **read-only audit + contract authoring** (no service installed, no bridge started, no proxy change, no production DB write)

---

## 摘要 / Summary

本轮回答四个问题：8791 桥接环境、7877 代理无人登录可行性、Inventory 正式接口合同、以及"新服务如何合法脱离 Agent 会话"。
Four questions answered: the 8791 bridge environment, 7877 proxy viability while logged off, the formal Inventory interface contract, and how a new service can legally outlive the agent session.

**核心结论 / Headline**: 会话内**不可能**创建脱离进程；必须由操作员用管理员权限一次性安装服务。桥接当前**未运行**（陈旧锁可自愈）。7877 **结构上支持**无人登录，但**未做真实注销验证**。
A detaching process **cannot** be created inside the session; the operator must install a service once with admin rights. The bridge is currently **not running** (self-healing stale lock). 7877 is **structurally** capable of serving while logged off, but **no real logoff test** was done.

---

## 关键字段 / Machine-readable verdicts

| 字段 / Field | 值 / Value | 依据 / Evidence |
|---|---|---|
| `BRIDGE_8791_LISTENING` | **false** | netstat 无 8791 行；无 pythonw 实例 |
| `BRIDGE_SUPERVISOR_RUNNING` | **false** | pid 24692 与子进程 48712 均已不存在 |
| `BRIDGE_STALE_LOCK` | **true** | lock 10-28 22:40:44，heartbeat 22:53:10（最后已知健康） |
| `BRIDGE_SELF_HEAL_ON_START` | **true** | `acquire_singleton()` 校验 pid+镜像名，回收陈旧锁 |
| `BRIDGE_REGISTRY_SEAL` | **SEAL_VERIFIED_FULL** | cfg/scope/4 entries 全匹配（按 registry 自身算法复算） |
| `BRIDGE_UNATTENDED_READY` | **false** | 仅 HKCU Run（登录触发）；无服务、无计划任务 |
| `BD_EXECUTION_HOST_VALID` | **false** | `pythonservice.exe` 不存在 → 僵尸服务 |
| `SCHEDULED_TASKS_UNATTENDED` | **false** | 全部 `LogonType=Interactive` |
| `PROXY_7877_UNATTENDED` | **SUPPORTED_BY_SERVICE_HOSTING** | 内核为 LocalSystem Auto 服务的子进程，Session 0 |
| `PROXY_7877_UNATTENDED_VERIFIED` | **false** | 未做真实注销测试 |
| `PROXY_7877_MODIFIED` | **false** | 本轮零改动 |
| `INVENTORY_ENTRYPOINT` | `bd_orchestrator.py --stage inventory --live` | argparse choices + stage_inventory |
| `INVENTORY_SCHEDULER_ID` | `automation-1784775229336` | ACTIVE，FREQ=HOURLY;INTERVAL=6 |
| `INVENTORY_LOCK_KEY` | `run_lock:daily_outreach:inventory:<business_date>` | bd_db.py:796/830 + 调用点 451/549 |
| `INVENTORY_LOCK_STALE_S` | **7200** | acquire_run_lock 默认值，与 channel_config.lock 一致 |
| `INVENTORY_BACKEND` | SQLite `data\bd_leads.db`（WAL，27 表，quick_check ok） | bd_db.DB_PATH |
| `INVENTORY_REQUIRED_PYTHON` | 系统 3.13.0 | 唯一装齐 requests/bs4/playwright/dnspython/lxml |
| `MANAGED_PYTHON_USABLE` | **false** | 3.13.14 全部依赖 MISSING |
| `SERVICE_INSTALLABLE_FROM_AGENT` | **false** | breakaway WinError 5；sc/schtasks/reg 全黑名单 |
| `SERVICE_REQUIRES_ADMIN_ONCE` | **true** | 唯一合法路径 |
| `ACTIONS_EXECUTED` | **0**（安装/启动/修改均为 0） | 见安全声明 |

---

## 四问四答 / Four answers

### Q1 · 8791 桥接环境与"合法脱离会话"

**现状**：未运行。无监听、无进程。残留锁与心跳属陈旧产物，启动时自愈。

**现有启动方式共三种，没有一种能在无人登录时工作**：
1. HKCU Run `RoktDeployChannelSupervisor` → managed `pythonw.exe` + `supervisor.py`（登录触发）
2. `bin/start_supervisor.cmd`（经 explorer 派发，注释明确目的是脱离 agent job）
3. `bin/launch_supervisor.vbs`（wscript 隐藏派发）

**没有** Windows 服务、**没有** `RoktDeployBridge` 计划任务（`CODEX_ENTRYPOINT.md` 第七节已过期）。

**执行身份**：当前 shell 为普通用户 `15690`（全部计划任务 `RunLevel=Limited`），会话内无管理员能力。

**Job Object**：无法用 API 直证（`Add-Type` 被拦），但三条间接证据充分——`start_supervisor.cmd` 注释、`launch_supervisor.vbs` 的 `bWaitOnReturn=False`、实测 `CREATE_BREAKAWAY_FROM_JOB` 返回 WinError 5。

**结论**：新服务必须在**会话外**由管理员安装。安装方式与取舍见 `SERVICE_INSTALLATION_BLUEPRINT_20261029.md`。

### Q2 · 7877 代理在无人登录时是否可用

**可用，判定码 `SUPPORTED_BY_SERVICE_HOSTING`。**

| 证据 | 内容 |
|---|---|
| 监听 | `127.0.0.1:7877` TCP+UDP，PID 30772 |
| 进程 | `MyClashCore.exe`，**SessionId = 0** |
| 父进程 | PID 7916 `MyClashHelperService.exe`（**Windows 服务**） |
| 服务 | `StartMode=Auto`、`StartName=LocalSystem`、`Running`、`D:\Clash Plus\MyClashHelperService.exe` |
| GUI | `MyClash.exe` PID 37524 Session 1（**非必需**） |

**为什么成立**：内核是自动启动 LocalSystem 服务的子进程，与桌面 GUI 生命周期解耦 → 无人登录时服务仍在，端口仍在听。

**必须标注的限制（不得夸大）**：`UNATTENDED_VERIFIED = false`。这是结构性推断，不是注销实测。

**实际环境约束**：
1. **D 盘依赖** — 代理在 `D:\Clash Plus`，D 盘未挂载则 7877 不监听
2. **仅回环** — 跨机不可用
3. **配置归 GUI** — 无人登录时无人能换节点或救死节点
4. **恢复策略不可读** — `sc.exe` 黑名单，不能假设 SCM 自愈
5. **Session 0 不读 HKCU** — `SCRAPER_PROXY` 必须注入服务环境

**未做任何代理修改**。`SCRAPER_PROXY=7877` 保持；`BD_MX_HTTPS_PROXY` 仍指 3213（死端口，靠 dnspython 兜底），**未动**，列为待人工决策项。

### Q3 · Inventory 正式接口合同

完整契约见 `INVENTORY_SERVICE_CONTRACT_20261029.json`，要点：

- **唯一入口**：`bd_orchestrator.py --stage inventory --live`，cwd 必须是项目目录，`--dry-run` 默认开启
- **调度权威**：`automation-1784775229336`（ACTIVE，6h 间隔 + 上次运行时长锚定）
- **锁**：`run_lock:daily_outreach:inventory:<business_date>`，`BEGIN IMMEDIATE`，`_acquired_at` UTC，2h 陈旧阈值，释放需 holder 匹配
- **backend**：SQLite `data\bd_leads.db`，WAL，27 表，`user_version=0`，`quick_check=ok`
- **运行时**：**系统 Python 3.13.0**（requests 2.34.2 / bs4 4.15.0 / playwright 1.62.0 / dnspython 2.8.0 / lxml 6.1.1）。**managed 3.13.14 依赖全缺，禁用**
- **发布器**：生产部署走 8791 `/v1/apply`（14 门禁，封印完整）；证据发布走 `workbuddy-task-window` git push
- **SHA**：11 个文件（含 `.env`）已冻结在契约 JSON 的 `file_sha256` 段

### Q4 · 自动发布脱敏证据

已通过现有交接机制写入 `handoff/workbuddy/production/`：4 个新文件 + 本次 commit。无凭据、无 token、无客户 PII、无原始日志。

---

## 未解决 / 明确标注为 UNKNOWN

| 项 | 状态 | 原因 |
|---|---|---|
| 7877 真实注销可用性 | `UNVERIFIED` | 需真实注销测试，会终止当前会话 |
| `MyClashHelperService` 恢复策略 | `UNKNOWN` | `sc.exe` 被黑名单拦截 |
| Agent 进程 Job 归属（API 直证） | `UNAVAILABLE` | `Add-Type` 被拦，仅有间接证据 |
| `BD_MX_HTTPS_PROXY` 是否应改 7877 | `PENDING_OPERATOR` | 超出本轮授权 |
| 桥接重启后能否存活跨 Agent 调用 | `UNVERIFIED` | 本轮未启动桥接（用户只要求检查环境） |

---

## 交付文件 / Delivered artifacts

| 文件 | 内容 |
|---|---|
| `BRIDGE_ENVIRONMENT_AUDIT_20261029.json` | 桥接运行态、执行身份、Job Object、启动方式、组件 SHA、封印校验 |
| `PROXY_UNATTENDED_VIABILITY_20261029.json` | 7877 托管链、判定码、5 条约束、失败模式 |
| `INVENTORY_SERVICE_CONTRACT_20261029.json` | 入口/锁/backend/运行时/流程/发布器/11 个文件 SHA |
| `SERVICE_INSTALLATION_BLUEPRINT_20261029.md` | 三条合法路径对比、安装清单、10 项验证表、回滚 |
| `PHASE1_SERVICE_READINESS_20261029.md` | 本文件（双语摘要 + 机器可读判定表） |

---

## 安全声明 / Safety

- 未安装服务、未注册计划任务、未改动 `sc.exe`/`schtasks.exe` 黑名单
- 未启动 8791 桥接、未调用任何 `/v1/*` 操作
- 未修改代理、`.env`、模板、代码、数据库 schema
- 数据库仅只读连接（`mode=ro`）用于 PRAGMA 与契约取证
- 未触碰 SMTP / 发送 / PreSend / Preflight / Outreach
- 未创建第二个 Inventory 调度
