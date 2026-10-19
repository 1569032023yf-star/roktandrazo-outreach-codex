# Codex 自主 BD 工程总控 / Autonomous BD Engineering Supervisor

日期 / Date: 2026-10-20。基线 / Baseline: `0ce0b10`。

## 当前授权 / Current authority

用户本轮总指令授权持续自主工程、独立工作线、受控发布和全部门禁满足后的 new_outreach。优先级覆盖历史阶段性“完成后停止”。开发隔离、资格标准、累计请求预算和生产受限通道继续有效。腾讯企业邮箱发信，Gmail仅内部收件。新客户发送仍需要真实地址、声明、退订、认证、资格、限额与完整发送链。

The current user instruction authorizes continuing engineering, separate workstreams, controlled releases, and new_outreach only after all gates pass. It supersedes old phase-specific stop instructions. Development isolation, qualification rules, cumulative request budgets and the restricted production channel remain effective. Tencent enterprise SMTP sends; Gmail is only the internal recipient. Customer outreach still requires a real address, truthful claims, unsubscribe handling, authentication, eligibility, limits and the complete send chain.

## 启动与调度 / Launch and scheduling

已实际运行 Codex CLI 非交互只读探针，返回 `AUTONOMY_LAUNCH_PROBE_OK`；当前 ChatGPT 登录可用。官方说明确认 `codex exec` 用于有界非交互任务：[OpenAI 非交互文档](https://learn.chatgpt.com/docs/non-interactive-mode)。应用心跳自动化 `rokt-razo` 已创建为 ACTIVE，每2小时回到本聊天执行有界周期。应用必须处于可运行状态；不声称机器关机或用户登出后仍运行。

A real read-only noninteractive Codex CLI probe returned `AUTONOMY_LAUNCH_PROBE_OK`; the existing ChatGPT login works. [Official noninteractive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) supports bounded `codex exec` jobs. App heartbeat `rokt-razo` was created ACTIVE every two hours in this chat. The app must be available to execute; operation while the computer is powered off or logged out is not claimed.

心跳是开发监督器，不是客户采集器；不改正式 Inventory `1784775229336`，不创建第二个采集调度器。每次最多45分钟，读取队列→选择工作→独立执行/审核→保存证据→退出。CLI固定登记总控只读审核、脱敏聚合遥测合同开发及后续独立审核。下一真实心跳可开发严格脱敏输入校验器，下一轮独立审查；无数据时仍UNKNOWN。开发成功只记needs_review，不自动通过审查或验收。不能把只读审核任务当成持续开发已经建成。

The heartbeat supervises engineering, not customer collection. It preserves production Inventory `1784775229336` and adds no collection scheduler. Each cycle is capped at 45 minutes: read queue, choose work, independently execute/review, save evidence and exit. Fixed CLI registrations cover supervisor review, sanitized aggregate telemetry contract development and its subsequent independent review. The next genuine heartbeat can develop the strict sanitized-input validator and the following cycle can review it; missing data remains UNKNOWN. Developer success becomes needs_review, never automatic review or acceptance. A review-only job does not prove sustained autonomous development.

## 执行方法 / Execution

在此工作树运行 / Run within this worktree:

```powershell
python autonomy/supervisor.py init
python -m unittest autonomy.test_supervisor -v
python autonomy/supervisor.py cycle
python autonomy/supervisor.py dashboard
```

只有真实应用心跳触发的执行才可记录 `cycle --source codex_heartbeat`，手动开发验收使用默认 manual。source标签本身不证明无人值守；必须匹配应用触发回执和任务实际进度。队列与逐周期证据保存在 Git 忽略的 `autonomy/runtime/`。队列运行使用独占文件锁，拒绝重复执行；崩溃遗留锁不按时间强删，先核实拥有进程及子进程已退出，再移除锁并让 running lease恢复排队。失败两轮标记复盘，三次失败阻止同任务无界重试。

Use `cycle --source codex_heartbeat` only inside an actual app heartbeat; manual validation uses the default manual source. Source labels do not prove unattended execution; match app trigger receipts and actual task progress. Queue and cycle evidence live in Git-ignored `autonomy/runtime/`. An exclusive file lock prevents duplicate execution. Never remove an orphan lock solely because of age: first verify the owning process and its children have exited, then remove the lock and requeue the persisted running lease. Two failures require reassessment; three block unbounded retries of that task.

CLI 子任务使用固定任务与角色注册：审核read-only sandbox，开发workspace-write sandbox，never approval、10分钟超时；不执行队列自带命令、不序列化异常文本或凭据。开发文件范围写入固定任务提示，workspace-write沙箱本身约束至工作树，并非逐文件ACL。Windows以挂起状态创建进程，加入kill-on-close Job后才恢复；超时、正常退出和监督进程崩溃均清理子孙进程，失败关闭。正式生产访问仅通过已有通道；新发布不能复用旧SAFE50 release。现通道只有四操作，无注册或生产指标接口，所以新发布登记和脱敏遥测输入仍是待接通能力。

CLI subtasks use fixed task/role registration: read-only review, workspace-write development, never approval and a ten-minute timeout. Queue content never supplies executable commands; exception text and credentials are not serialized. Developer file scope is in the fixed prompt; workspace-write restricts the worktree rather than providing per-file ACLs. Windows starts the process suspended and assigns a kill-on-close Job before resuming it; timeout, normal exit and supervisor crashes clean up descendants and fail closed. Production access uses only the existing channel. New releases cannot reuse the old SAFE50 release. The current channel exposes four operations without registration or telemetry, so new release registration and sanitized production metrics remain missing capabilities.

## 分工与合并 / Roles and integration

Developer/Tester分线工作树执行，父代理独立审核最终差异、业务门禁和失败路径；CLI另作独立总控审查。Release Manager串行组织发布，不改桥接权限/配置，不直调生产执行器。A/B/C所有变更通过审核后才选择性合并；未合并工作树互不覆盖。正在运行的工作线不得被心跳同时重写。

Developer/Tester work in separate worktrees. The parent independently reviews final diffs, business gates and failure paths, with an additional CLI supervisor review. The Release Manager serializes deployment, without modifying bridge permissions/configuration or directly invoking the production executor. Integrate A/B/C selectively only after review; active worktrees must not be concurrently rewritten by the heartbeat.

## 业务口径与验收 / Metrics and acceptance

日报列出24小时与7天组织、官网、第一方邮箱、历史/MX资格、SAFE、发送、回复、退信与退订。缺获准生产数据源一律UNKNOWN；旧44候选、2官网、1邮箱或SAFE56不可计为当日新增。品牌线本次实时核验结果需单独记录，不与生产总量混用。

The daily report distinguishes 24-hour and seven-day organizations, official sites, first-party emails, history/MX qualification, SAFE, sends, replies, bounces and unsubscribes. Missing authorized production data stays UNKNOWN. Historical 44 candidates, two sites, one email or SAFE56 are not today's additions. Record current brand validation separately from production totals.

两个连续2小时真实自动周期尚未发生，不能通过两次手动调用、压缩模拟或审核探针替代。验证JSON保持 `TWO_UNATTENDED_CYCLES_VERIFIED=false` 和 `AUTONOMOUS_OPERATIONS_ACTIVE=false`，直到所有用户条件逐一满足。代码中的保守判定不会自动把自报标签升级为真实调度证明。

Two consecutive real two-hour automated cycles have not occurred. Two manual calls, compressed simulation or review probes cannot replace them. Keep `TWO_UNATTENDED_CYCLES_VERIFIED=false` and `AUTONOMOUS_OPERATIONS_ACTIVE=false` until every user acceptance condition is satisfied. Conservative code never promotes self-reported source labels into authenticated scheduling evidence.

## 未执行、风险与下一步 / Non-executed work, risks and next steps

未执行新生产部署、客户发信、生产数据库读写、权限变更；生产业务指标未知。下一步独立审核各工作线，修复审核发现，核查受控发布登记入口，等待真实心跳周期并保存证据。若启动入口失效或同阻塞两轮，继续其他合法任务，并仅对新权限/凭据/重大业务决定升级用户。报告自检：双语、含结果/未执行/风险/下一步，无凭据，无未完成冒充完成。

No new production release, customer email, production database read/write or permission change has been executed. Production metrics are unknown. Next independently review each stream, repair findings, verify the controlled registration interface, and collect genuine heartbeat evidence. If launch fails or a blocker repeats twice, continue other authorized work and escalate only new permissions, credentials or major business decisions. Report self-check: bilingual, results/non-executed work/risks/next steps included, no credentials and no incomplete work labeled complete.
