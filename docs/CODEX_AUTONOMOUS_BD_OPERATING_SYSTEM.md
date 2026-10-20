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

最近两个可信心跳04:44与06:48分别匹配不同周期的开发及独立审核完成回执，间隔7472.05秒，无用户重新下达指令。控制代理已比对可信聊天触发元数据、任务ID、开始结束时间及输出哈希，TWO_UNATTENDED_CYCLES_VERIFIED=true。单独source标签仍不作为真实性证明；supervisor.py中的保守辅助函数不会自行提升该状态。两周期只是整体验收的一项，真实feed、新发布登记及持续并行未齐备，AUTONOMOUS_OPERATIONS_ACTIVE=false。

The latest trusted heartbeats at 04:44 and 06:48 match distinct completed developer/reviewer cycle receipts, 7472.05 seconds apart, without a new user command. The controller matched trusted chat trigger metadata, task IDs, start/end timestamps and output hashes; TWO_UNATTENDED_CYCLES_VERIFIED=true. A source label alone remains insufficient, and the conservative helper in supervisor.py does not promote this state itself. Two cycles satisfy only one overall criterion. Real feed, new release registration and sustained parallel operation remain incomplete, so AUTONOMOUS_OPERATIONS_ACTIVE=false.

## 未执行、风险与下一步 / Non-executed work, risks and next steps

未执行新生产部署、客户发信、生产数据库读写、权限变更；生产业务指标未知。下一步独立审核各工作线，修复审核发现，核查受控发布登记入口，等待真实心跳周期并保存证据。若启动入口失效或同阻塞两轮，继续其他合法任务，并仅对新权限/凭据/重大业务决定升级用户。报告自检：双语、含结果/未执行/风险/下一步，无凭据，无未完成冒充完成。

No new production release, customer email, production database read/write or permission change has been executed. Production metrics are unknown. Next independently review each stream, repair findings, verify the controlled registration interface, and collect genuine heartbeat evidence. If launch fails or a blocker repeats twice, continue other authorized work and escalate only new permissions, credentials or major business decisions. Report self-check: bilingual, results/non-executed work/risks/next steps included, no credentials and no incomplete work labeled complete.

## 本轮整合边界 / Current integration boundary

城市候选来源提交 `6ce6e317` 基于93a8d0a，整合提交860728f保留5A的identity_review终态。附带patch/manifest记录的是独立候选源码，不是整合后文件的生产哈希；正式发布前必须按真实生产基线重新生成并登记，不能直接套用旧清单。品牌提交5e9b89d仅在完整依赖的独立分支验证，5A缺该依赖栈，禁止把单提交通过说成整合成功。

City source candidate 6ce6e317 is based on 93a8d0a. Integration 860728f preserves 5A's identity_review terminal state. Its patch/manifest describe isolated candidate sources, not production hashes for integrated files. Regenerate and register against the actual production baseline before release rather than applying the old manifest. Brand commit 5e9b89d was verified only on its complete dependency branch; 5A lacks that stack, so a passing isolated commit is not successful integration.


字节传输复查：59b673c把城市候选及内部QA补丁登记为Git -text；两清单SHA与磁盘一致，并在core.autocrlf=true的新检出中保持逐字节一致。完整V6分支150ba3c与根整合1356dde的回归记录见handoff/phases/AUTONOMY_V6_VALIDATION_20261020.json，完整套件未全绿。上一轮因额度限制中断的收尾由本轮心跳恢复，不把中断补记为成功。

Byte-transport verification: commit 59b673c marks city and internal-QA candidate patches as Git -text. Both manifest SHAs match disk and remain byte-identical in fresh core.autocrlf=true checkouts. V6 branch 150ba3c and root integration 1356dde use the regression evidence in handoff/phases/AUTONOMY_V6_VALIDATION_20261020.json; the complete suite is not green. This heartbeat recovered closeout interrupted by usage limits, without retroactively marking that interruption successful.


04:48本轮结果：限定遥测合同开发真实完成，18项离线合成测试及父独立复跑均通过；任务保持needs_review，独立Reviewer已排入下次心跳。确认成功无人值守周期为1，非2；本轮仅一项队列工程，当前没有两条无人值守工作线并发，PARALLEL_WORKSTREAMS_ACTIVE=false，三条独立工作线的历史能力演练另列。内部QA正式预检在04:47复查仍为400 UNKNOWN_RELEASE_ID。整体AUTONOMOUS_OPERATIONS_ACTIVE=false，下一步独立审核遥测合同，缺真实feed继续UNKNOWN。

04:48 outcome: bounded telemetry-contract development actually completed; 18 synthetic offline tests and the parent's independent rerun passed. The task remains needs_review with the independent Reviewer queued for the next heartbeat. Confirmed successful unattended cycles equal one, not two. Only one queued engineering task ran this heartbeat; two unattended workstreams are not currently concurrent, so PARALLEL_WORKSTREAMS_ACTIVE=false, with prior three-agent capability recorded separately. Supported QA preflight rechecked at 04:47 still returned 400 UNKNOWN_RELEASE_ID. Overall AUTONOMOUS_OPERATIONS_ACTIVE=false. Next independently review the contract; without a real feed, metrics stay UNKNOWN.


06:50最新状态 / Latest status at 06:50: 遥测合同独立只读审核无发现，34项纯内存合成断言通过；Reviewer审查了既有18项测试源码，但未执行其写临时文件的套件。受控QA预检仍为400 UNKNOWN_RELEASE_ID。两轮相同阻塞已复盘：保留已有登记申请，不重复升级或改权限；下次真实心跳执行固定5e9b89d的B-brand-dependency-audit，先做只读导入依赖审核再确定最小迁移。未读取生产DB、真实inbox或发送邮件，业务指标仍UNKNOWN。

Independent read-only telemetry review found no issues and passed 34 in-memory synthetic assertions. The Reviewer inspected the existing 18-test source but did not execute its temporary-file-writing suite. Supported QA preflight remains 400 UNKNOWN_RELEASE_ID. Reassessment after two unchanged blocker cycles retains the existing registration request without duplicate escalation or privilege changes. Next genuine heartbeat runs B-brand-dependency-audit at pinned 5e9b89d to audit import dependencies before minimal integration. No production DB or real inbox was read and no email was sent; business metrics remain UNKNOWN.


## 2026-10-20 08:56+08 品牌依赖审核 / Brand dependency audit

本轮真实心跳00:52:39.151Z对应周期c35de6c2-5533-452f-9930-9ecead4457c3，00:52:55Z开始、00:56:38Z完成。独立Git/AST审核确认15模块、4入口、6测试共25个文件可新增；115仅为测试方法数，本轮未执行品牌测试。静态接口兼容不等于运行通过。完整发现与证据见docs/AUTONOMY_BRAND_DEPENDENCY_AUDIT.md。总控14项回归通过，覆盖两类开发任务的审核排队。

The genuine 00:52:39.151Z heartbeat matched cycle c35de6c2-5533-452f-9930-9ecead4457c3, starting at 00:52:55Z and completing at 00:56:38Z. Independent Git/AST review identified 25 additive files: 15 modules, four entrypoints and six tests. 115 counts test methods; no brand tests executed this cycle. Static API compatibility does not prove runtime success. Full findings and evidence are in docs/AUTONOMY_BRAND_DEPENDENCY_AUDIT.md. All 14 supervisor regressions passed, covering review queuing for both developer task types.

下一步：下次真实心跳新增固定来源25文件，禁网测试后进入needs_review，再排独立审核；保留较新5A/城市/V6代码。三轮真实自动任务完成，两连续周期条件保持true；整体自主运行及持续并行仍false。未复查生产通道，最近健康/QA预检证据仍分别为06:49/06:50；不把历史状态称为当前实测。无生产DB、部署、采集或发信，指标UNKNOWN，旧SAFE56不算新增。

Next: Next genuine heartbeat adds 25 pinned-source files, runs offline tests and enters needs_review before independent review; preserve newer 5A/city/V6 code. Three genuine automatic tasks are complete and the consecutive-cycle condition remains true; overall autonomy and sustained parallel operation remain false. Production channel was not rechecked: health/QA evidence remains timestamped 06:49/06:50, not a current measurement. No production DB access, release, discovery or sending occurred; metrics remain UNKNOWN and historical SAFE56 is not new growth.
