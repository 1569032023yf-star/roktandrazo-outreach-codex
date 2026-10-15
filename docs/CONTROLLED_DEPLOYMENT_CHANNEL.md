# 受控部署通道配置交接 / Controlled Deployment Channel Configuration

## 当前状态 / Current status

### 2026-10-15 实际连接更新 / Live connection update

已发现并由 Codex 实际连接 `rokt-deploy-channel` v1.0.0：`http://127.0.0.1:8791`。固定入口交接包位于本机 `C:\Users\15690\WorkBuddy\deploy-channel\CODEX_ENTRYPOINT.md`。凭据只从 Windows 凭据管理器目标 `rokt-deploy-channel:bridge-token` 读取并保留内存，禁止输出。现有凭据指纹与本地交接包一致；桥接监听仅回环，进程使用 WorkBuddy 用户身份，API 身份仅允许注册发布的四操作；这不是独立的低权限 Windows 账户。执行器 ACL 对 CodexSandboxUsers 为 ReadAndExecute。

Codex discovered and actually connected to `rokt-deploy-channel` v1.0.0 at `http://127.0.0.1:8791`. Its local entry-point handoff is `C:\Users\15690\WorkBuddy\deploy-channel\CODEX_ENTRYPOINT.md`. Read credentials only from Windows Credential Manager target `rokt-deploy-channel:bridge-token`, retain them in memory, and never print them. Credential fingerprint matches the local handoff; the listener is loopback-only. The bridge runs as the WorkBuddy user, with an API identity limited to four registered-release operations; it is not a separate low-privilege Windows account. Executor ACL grants CodexSandboxUsers ReadAndExecute.

Codex 独立实测：缺少/错误凭据为 401；任意命令/文件端点为 404；路径穿越、未知发布、未确认 apply、未知 status/rollback 为 400；错误 HTTP 方法为 404。10 项全部通过，调用均有审计。2026-10-15 10:39:57 +08 实时 preflight 为 14/14，通过固定 before-SHA、精确补丁和逆向验证；SMTP=0，发送任务暂停。该快照不能替代以后发布的实时检查。状态查询及回滚接口存在，真实业务回滚尚未执行；先前 WorkBuddy 沙箱验收报告只作为补充证据。

Codex independently tested missing/incorrect credentials (401), arbitrary command/file endpoints (404), traversal, unknown release, unconfirmed apply, unknown status/rollback (400), and the wrong HTTP method (404). All ten checks passed and calls were audited. Live preflight at 2026-10-15 10:39:57 +08 passed 14/14, including pinned before-SHA, exact patch, and reverse verification; SMTP=0 and sending tasks paused. This snapshot cannot replace future live checks. Status and rollback interfaces exist; no actual business rollback has been executed. The earlier WorkBuddy sandbox acceptance report is supplementary evidence only.

后续正常发布默认复用该入口；每次仍先认证、核实固定发布、实时 preflight 和备份/互斥/回滚门禁。禁止直接 CLI 调用执行器替代桥接，禁止修改执行策略或开发隔离变量。以下 2026-10-14 无通道记录为历史状态，已由本更新取代。首次发布及生产计划验收见 handoff/phases/PHASE4A8S_CONTROLLED_RELEASE_20261015.md。

Reuse this entry point by default for subsequent routine releases, while authenticating, verifying the registered release, and checking live preflight, backup, exclusion, and rollback gates every time. Do not replace the bridge with direct executor CLI invocation or change execution policy/development isolation variables. The 2026-10-14 unavailable-channel record below is historical and superseded. See handoff/phases/PHASE4A8S_CONTROLLED_RELEASE_20261015.md for first release and scheduled acceptance status.

2026-10-14 当前工具没有 WorkBuddy BD 发布接口。Windows 只读服务查询确认 BDExecutionHost 为 Stopped / Manual，未返回 RoktDeploymentExecutor；不排除其他尚未提供的通道。Get-PSSessionConfiguration -Name RoktDeployment 返回 Access denied，要求管理员会话，故端点是否存在未核实。旧 phase4a_deploy.py 固定旧提交并覆盖六个文件，不符合 P1 单文件范围，不得运行。不得启动旧业务服务或独立 Inventory 循环作为替代通道。

On 2026-10-14, available tools expose no WorkBuddy BD release interface. A read-only service query returned BDExecutionHost as Stopped / Manual and no RoktDeploymentExecutor; this does not rule out an undisclosed channel. Get-PSSessionConfiguration -Name RoktDeployment returned Access denied requiring an administrator session, so endpoint existence remains unverified. The old phase4a_deploy.py pins an older commit and overwrites six files, outside P1's single-file scope; do not execute it. Do not start the old business service or a separate Inventory loop as a substitute.

## 一次性接入 / One-time connection

管理员先核实已有正式通道并优先复用。否则配置独立受限部署执行器或受限端点。本次交付是接入要求和冻结发布清单，尚无端到端验收的安装器或生产执行器；不能把文档、清单或调用方自报 safe=true 当作发布凭据或真实门禁。

An administrator should verify and reuse an existing authorized channel first, otherwise configure a separate restricted release executor or endpoint. This delivery supplies connection requirements and a pinned manifest, not an end-to-end accepted installer or production executor. Documents, manifests, and caller-asserted safe=true are neither release credentials nor live gates.

| 配置项 / Item | 要求 / Requirement |
|---|---|
| 身份 / Identity | 独立受限身份；凭据留在本机受保护存储，不进入聊天或 Git / Separate restricted identity; credentials stay in protected local storage, outside chat and Git |
| 固定目标 / Fixed target | `C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach\bd_orchestrator.py`；发布前由正式入口核实实际运行路径 / Verify actual runtime path through the authorized entry point |
| 写入 / Writes | 仅目标文件及独立备份、审计目录；拒绝任意路径、代码、命令 / Only target file and dedicated backup/audit directories; reject arbitrary paths, code, and commands |
| 接口 / Interface | preflight(release_id), apply(release_id), status(operation_id), rollback(operation_id)；返回非敏感结构化证据 / Return structured non-secret evidence |
| 门禁 / Gates | 执行器直接读取实际文件、发送冻结、唯一 Inventory 的实时计划和执行状态 / Executor directly reads actual files, sending freeze, and the sole Inventory's live schedule/execution state |
| 并发 / Concurrency | 最终检查至替换后核验持有与 Inventory 协调的互斥；处理 UTC 日期锁、跨午夜竞态，不抢占有效锁 / Hold exclusion coordinated with Inventory through verification; handle UTC date locks and midnight races, never steal valid locks |
| 备份替换 / Backup and replace | 备份重读 SHA；同卷临时文件 fsync、原子替换、目标重读 SHA；保留 ACL；替换前重核源 SHA / Re-read backup SHA; fsync same-volume temporary file, atomically replace, re-read target SHA; preserve ACL and recheck source SHA before replacement |
| 回滚 / Rollback | 当前 SHA 必须为已知 after、备份必须为已知 before；同样核实窗口、锁、发送冻结 / Require known after/current and before/backup fingerprints and verify window, locks, and sending freeze |
| 调度 / Scheduling | 保留唯一 Inventory 1784775229336 和预算，不创建发送或采集调度器 / Preserve the sole Inventory and budget; create no sending or collection scheduler |

管理员一次性核实通道可用后，提供入口标识、受限动作、受限身份已获访问的证明和一次无写入 preflight 的结构化结果。Codex 随后负责普通发布，无需每版批准。开发护栏、隔离变量不变。新建执行器先在测试目录验证拒绝任意路径、权限范围、备份失败、替换失败、回滚失败和 Inventory 启动竞态，验收后再接入真实固定目标。

After one-time verification, provide the endpoint identifier, restricted actions, proof of identity access, and the structured result of one read-only preflight. Codex then owns routine releases without per-version approval. Leave development guards and isolation variables unchanged. Test arbitrary-path rejection, permissions, backup/replacement/rollback failures, and Inventory startup races in a test directory before accepting a new executor against the fixed production target.

## P1 首次发布 / First P1 release

一次性管理员核实可在已有管理员 PowerShell 会话执行以下只读命令。不要修改执行策略。tools/inspect_deployment_channel.ps1 具有相同诊断用途，已静态解析通过，但当前系统禁止脚本执行，因此没有完成脚本运行验收。JEA 注册需要管理员权限，见 [Microsoft 官方配置说明](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/jea/register-jea)。以下查询并不安装或建立通道；若通道不存在，仍需按上表配置并验收执行器。

For one-time administrator verification, run the following read-only commands in an existing administrator PowerShell session. Do not change execution policy. tools/inspect_deployment_channel.ps1 provides equivalent diagnostics and passes static parsing, but current policy blocks script execution, so runtime acceptance is incomplete. JEA registration requires administrator rights; see [Microsoft's configuration documentation](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/jea/register-jea). These queries do not install or establish a channel; a missing executor still requires configuration and acceptance against the table above.

```powershell
Get-CimInstance Win32_Service -Filter "Name = 'BDExecutionHost' OR Name = 'RoktDeploymentExecutor'" | Select-Object Name, State, StartMode
Get-PSSessionConfiguration -Name 'RoktDeployment' | Select-Object Name, PSVersion
```

冻结清单为 patches/production/phase4a8s/release_request.json。一个文件、三个补丁块，严格校验字节。verify_production_patch.py 仅用于开发副本离线演练，不是生产执行器。真实 SHA 不匹配立即停止，不强制覆盖。通道接入后：实时 preflight → 门禁及互斥 → 备份核实 → 精确转换及原子替换 → 目标 SHA 核验 → 释放互斥 → 等待原有 Inventory 下一次正常计划运行 → 验收请求、组织、线索、邮箱、SAFE、城市及异常。实际运行证据未取得前，不宣称生产恢复。

The pinned manifest is patches/production/phase4a8s/release_request.json. Require one file, three hunks, and exact bytes. verify_production_patch.py is an offline development-copy rehearsal tool, not a production executor. Stop on actual SHA mismatch; never force replacement. After connection: live preflight, gates and exclusion, verified backup, exact transform and atomic replacement, target SHA verification, release exclusion, await the existing Inventory's next normal scheduled run, and accept requests, organizations, leads, emails, SAFE/city changes, and exceptions. Do not claim production recovery before obtaining actual runtime evidence.
