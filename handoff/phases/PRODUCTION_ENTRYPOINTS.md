# 生产入口与写入路径 / Production Entrypoints and Mutation Paths

日期 / Date: 2026-09-08。全部依据开发副本 / All evidence from development copy.

中文：本表区分当前代码接线、可执行的辅助入口和历史材料。没有读取 Windows 注册任务或 WorkBuddy 在线配置，不能把脚本中的 schedule 常量当成已经注册的真实调度器。完整逐文件候选清单见 `audit_evidence/STATIC_ENTRYPOINT_WRITER_INDEX.md`；每个文件的函数/导入见 `static_inventory.json`。

English: This inventory distinguishes current code wiring, callable auxiliary entrypoints and historical records. Windows task registrations and online WorkBuddy configuration were not inspected; schedule constants do not prove active scheduler registration. Full per-file candidates and function/import indexes are in `audit_evidence`.

## 运行入口 / Runtime entrypoints

| 入口 / Entry | 作用与副作用 / Role and side effects | 审计定位 / Evidence |
|---|---|---|
| `bd_orchestrator.py --stage ...` | inventory/pre-send/outreach/post-send/end-of-day/morning/status；live 写作业与业务数据。 / Central stage CLI; live mode writes jobs/business state. | `main:737`, stage functions |
| `daily_session.py` | 独立 CLI 与 FSP 消费函数；历史 session 分支仍存在。 / CLI plus frozen-plan executor; legacy session branches remain. | `execute_final_send_plan:72`, CLI at file end |
| `bd_sender.send_one`, `batch_send` | 低层发送 API 默认 dry_run=False，必须把调用方视为执行边界。 / Lower-level sending API defaults to live; caller is an execution boundary. | `bd_sender.py:498,727` |
| `BDExecutionHost` | Windows 服务启动/监控 Delivery Guard 与 Ops Center，后者嵌入 Poller；install/remove 会修改服务。 / Windows service manages child processes; install/remove mutate service registration. | `bd_execution_host_service.py:114,359,453,493` |
| `bd_review_server.py` | HTTP 8765；审核/拒绝/延期/手工邮箱/FB 队列写库，main 启动 Poller。 / Review HTTP server with mutating endpoints and embedded poller startup. | `api_approve:206`, `api_manual_email:232`, `main:1069` |
| `bd_delivery_guard.py` | 电源保活、状态/PID、进程和计划任务相关调用。 / Power guard and runtime/process interactions. | static process index |
| `bd_ops_poller.start_poller` | tracking、心跳；非 SAFE_UNATTENDED_MODE 还有 health/reply/bounce/suppression/delivery_guard。 / Tracking/heartbeat plus other loops depending on mode. | `bd_ops_poller.py:475` |
| `result_recovery_sync.py`, `daily_results_0900.py`, `post_send_reconciliation.py` | 回流与报告，对账可写；不能凭文件名认定只读。 / Recovery/reporting with possible writes. | SQL/wrapper inventory |
| `inventory_monitor_executor.main` | 另一个 standalone 富集循环，直接更新 leads；SEND_ENABLED=False 仅表示自身不发信。 / Independent enrichment writer; false send flag does not imply no DB mutation. | `main:590`, `safe_write_a0:154` |
| `discovery/providers/browser_maps_scraper.py` | 独立 Playwright 抓取 CLI，写缓存结果；不自动证明后续已入库。 / Browser CLI writes discovery results; not equivalent to completed ingestion. | scraper CLI and cache functions |
| `manual_email_workflow.py`, `bd_review_cli.py`, `review_workflow.py` | 人工/富集提交、审核状态和历史记录。 / Submission/review and history persistence. | workflow entrypoints |
| `email_tracking_server.py`, `cloudflare/src/*` | 本地跟踪/webhook 与云打开跟踪入口；本地映射 unsubscribe 事件，Worker 未发现退订路由。 / Local tracking/webhook and cloud open-tracking entrypoints; local unsubscribe event mapping is not a Worker unsubscribe route. | `email_tracking_server.py:222`; Worker `/o/`, `/healthz`, `/internal/mx-check`, `/internal/dashboard-summary` |
| `fb_fallback_recovery.py`, `facebook_enrichment/*`, import/audit/migration scripts | 辅助抓取/批量写入/迁移，不能直接运行。 / Auxiliary fetching, bulk writes and migrations. | full static index |

## 调度与服务 / Schedulers and services

中文：`install_windows_tasks.ps1.audit-disabled` 定义五个每天的 Windows Task Scheduler 任务：RoktRazo-BD-Inventory 15:00、PreSend 22:30、Outreach 23:00、PostSend 00:10、EndOfDay 00:25。脚本写死生产工作目录和 WorkBuddy Python，还先 unregister 再 register；开发中不得运行。

English: The disabled task installer defines five daily Windows tasks: Inventory 15:00, PreSend 22:30, Outreach 23:00, PostSend 00:10 and EndOfDay 00:25. It hardcodes production paths and unregisters/re-registers tasks. It must not run from development.

中文：service 文件虽有 SEND_SCHEDULE 与 bookmark 常量，但当前 `SvcDoRun` 主循环只监控组件/写心跳，没有引用 SEND_SCHEDULE 执行阶段。不能宣称服务本身已经承担五阶段调度。其 `_create_poller_script` 辅助函数还内嵌生产绝对路径，虽然当前组件配置采用 embedded 模式。

English: The service defines SEND_SCHEDULE and bookmark constants, but its main loop only monitors components and heartbeats; no schedule dispatch references these constants. The service cannot be claimed to run the five stages itself. Its unused inline-poller helper also embeds an absolute production path despite the current embedded mode.

中文：副本保留 20 个 WorkBuddy automation 目录的历史记录，以下为全部目录映射；名称为历史标题的功能归纳，激活状态均未实时验证。

English: The copy contains histories for 20 WorkBuddy automation directories. All are mapped below; roles summarize historical titles, and active registration status is unverified.

| Automation ID | 历史用途 / Historical role |
|---|---|
| 1782369770937 | 每日发送 / Daily send |
| 1782800192924 | 早期发送执行 / Earlier send execution |
| 1784775222119 | 发送后 / Post-send |
| 1784775229336 | 15:00 库存 / Inventory |
| 1784775236108 | 日终 / End-of-day |
| 1785315431197 | 22:30 预发送计划 / Pre-send plan |
| 1785315443554 | 22:55 预检 / Preflight |
| 1785315456598 | 23:00 外联 / Outreach |
| 1785315468925 | 00:10 对账 / Post-send verification |
| 1785406176740 | 每日结果 / Daily results |
| 1785720738893 | 周末上午库存 / Weekend AM inventory |
| 1785720747436 | 周末下午库存 / Weekend PM inventory |
| 1785749958394 | 每日采集报告 / Collection report |
| 1785751625030 | 一次性晚间预发送 / One-off evening pre-send |
| 1785751634298 | 一次性晚间预检 / One-off evening preflight |
| 1785751645486 | 一次性晚间发送 / One-off evening send |
| 1785804406748 | 旧生产预发送 / Older production pre-send |
| 1785804413719 | 旧生产预检 / Older production preflight |
| 1785804421539 | 旧生产外联 / Older production outreach |
| 1786002601925 | 08:45 结果回流 / Result recovery sync |

中文：09-04 的历史报告称七个旧 automation 暂停、两个旧 Windows task（Roktandrazo_Daily_Outreach、RoktRazo-BD-Daily-Outreach）disabled，永久清理未执行。该报告对库存触发时间的 UTC 解释存在问题，不能整体当作今天的事实。快照 09-06 有两次 inventory（目标分别 30、60），证明同日多次运行，不证明并发或重复发送。

English: A September 4 report says seven old automations were paused and two old Windows tasks disabled, with permanent cleanup unexecuted. Its UTC interpretation is problematic and it is not current registration evidence. Two September 6 inventory jobs with targets 30 and 60 prove repeated daily execution, not concurrent execution or duplicate emails.

## DB 写入清单 / DB writer inventory

中文：以下为非历史业务文件的写入分组，包括间接调用；逐 SQL 行号见完整索引。历史脚本、测试、backup/data 内嵌源码也在完整索引内，不因目录叫 backup 就推定不可执行。

English: The following groups include direct and indirect writers outside historical copies. Exact SQL line candidates are in the full index, including backup/test/data-embedded sources; directory names do not make code non-executable.

| 写入集合 / Writer set | 数据对象 / State |
|---|---|
| `bd_db.py` | leads、send_log、suppression、配置/锁、作业、审核、schema migrations / Primary business tables, configuration/locks, jobs and schema |
| orchestrator、daily_session、sender、final_send_plan | job/config/lock、计划、授权、发送记录与商户状态 / Jobs, plans, authorizations, send history and lead state |
| `discovery_service`, `retail_city_queue`, `agent_lead_collector`, `brand_candidate_importer` | discovery staging/hits/query/provider audit、城市游标、lead 插入 / Discovery/city state and lead insertion |
| `manual_email_workflow`, `review_workflow`, `bd_review_server` | leads、审核/提交/邮箱替换历史、manual queue、FB queue / Lead review/submission/history and queues |
| `inventory_monitor_executor`, `agent_email_verifier`, `browser_verifier`, `fb_fallback_recovery`, `b_pool_*`, candidate `b_pool_enrichment` | 邮箱、分级、验证/证据、候选库、状态 / Email, quality, evidence and pool state |
| `bounce_pipeline`, `bd_ops_poller`, `result_recovery_sync`, `post_send_reconciliation`, `update_bounce_db`, `agent_supervisor` | bounce/reply/suppression、回流状态、修复/抑制和控制配置 / Delivery/reply/suppression and control state |
| `preflight_gate.py:90,283` | 默认缓存持久化可能写 system_config；CLI 有 --no-cache-write。 / MX cache may persist by default; explicit no-cache-write option exists. |
| `email_engagement/local_first_party_provider.py`, `plunk_poc_provider.py`, `email_tracking_server`, cloud Worker | SQLite tracking 元数据及云端 D1 tracking；Worker `cloudflare/src/index.js:81,87` 写入 `tracking_events`、更新 `tracking_messages`，未发现 D1 suppression 写入。 / Local tracking metadata and remote D1 tracking; Worker lines 81 and 87 insert tracking_events and update tracking_messages, with no D1 suppression writer found. |
| `db.py`, `phase1_db.py`, `config.py` consumers, old imports/collector/drafter | 旧 leads.db/phase1_leads.db 与部分 bd_leads.db / Multiple legacy database authorities |
| `db_migration_v2.py`, `migrations/*`, `lead_audit_cleanup.py`, `timezone_resolver.py` | schema/data migration、删除/更新、时区回填 / Schema/data migration, deletions/updates and timezone backfill |

## SMTP 与外部写入 / SMTP and external mutation paths

中文：主客户路径为 daily_session → bd_sender.send_one → `_create_connection`（SMTP_SSL）→ `sendmail:618`。同文件另有发送者自检副本 `sendmail:681`、IMAP Sent 追加 `_save_to_sent`，以及 `_activate_tracking:269` 用 npx/wrangler `--remote` 更新 D1。它们都是实际外部副作用，mock 主 sendmail 不够。

English: The primary customer path is daily_session → bd_sender.send_one → SMTP_SSL → sendmail at line 618. The same file sends a self-check copy at line 681, appends IMAP Sent mail and remotely updates D1 via npx/wrangler. Mocking only customer sendmail does not isolate these external writes.

中文：`sender.py` 仍含 SMTP/sendmail，但顶部只在 BD_TEST_MODE 不为 true 时抛异常；设为 true 会解除旧入口禁用，test mode 不是全局无网络开关。`send_phase2.py`、`send_phase3.py` 也有同类门禁；main/pipeline 仍引用旧 sender。完整索引列出归档中的所有 SMTP 候选，调用可达性需结合顶部门禁判断。

English: Legacy sender retains SMTP and is blocked only when BD_TEST_MODE is not true. Setting it true unlocks legacy code; test mode is not a global no-network switch. Phase2/3 use related guards and main/pipeline retain legacy calls. The full index lists historical SMTP candidates; reachability depends on their guards.

中文：冻结发送器另有高风险配置路径：test_mode=true 但 test_email 为空时，绕过 authorization 块而 actual_to 保持客户邮箱；真实 sendmail 发生后才检查 real_plan=None。本次只报告，不修改冻结文件，也未重现发送。

English: A high-risk configuration path exists in the frozen sender: test mode with an empty test recipient skips authorization while retaining the customer address; the missing real-plan check occurs after sendmail. This was reported without modifying frozen code or reproducing a send.
