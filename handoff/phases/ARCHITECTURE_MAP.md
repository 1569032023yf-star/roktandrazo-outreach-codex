# 运行架构审计 / Runtime Architecture Audit

日期 / Date: 2026-09-08。范围 / Scope: Phase 1，开发副本静态审计 / development-copy static audit.

## 边界与证据 / Boundaries and evidence

生产根 / Production root: `C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach`。
开发根 / Development root: `C:\Users\15690\Documents\ChatGPT\线下\roktandrazo-outreach-dev`。

中文：完整复制后，所有代码读取和分析仅在开发根进行。Robocopy 清单共 1,425 文件、873.80 MiB 左右、失败 0；返回码 1 表示成功复制。未修改生产文件、数据库、服务、自动化或运行 SMTP。源目录在复制时可能仍被其他进程使用；普通文件复制不是数据库事务时间点快照。开发快照 `PRAGMA integrity_check=ok`，但这不证明全目录跨文件一致性。本次未连接任何外部服务。

English: All code reading and analysis after copying occurred inside the development root. Robocopy reported 1,425 files, approximately 873.80 MiB, zero failures; exit code 1 means files copied successfully. No production files, database, services, automations or SMTP were changed or invoked. Other processes may have been active during copying; a file copy is not a transaction-consistent database snapshot. The development snapshot passes `PRAGMA integrity_check`, which does not establish cross-file consistency. No external services were contacted.

中文：静态分析覆盖 487 个 Python 文件（含历史副本和测试），其中两个历史 `_simple_check.py` 语法错误。未导入项目模块、未运行现有测试。函数、导入、CLI、SQL 写入和进程调用的完整候选索引见 `audit_evidence/static_inventory.json` 和 `audit_evidence/STATIC_ENTRYPOINT_WRITER_INDEX.md`。候选索引包含假阳性；动态导入、外部调度注册和进程当前状态无法仅凭副本穷尽。

English: Static analysis covers 487 Python files including historical copies and tests; two historical `_simple_check.py` files have syntax errors. Project modules and existing tests were not executed. Full candidate indexes of functions, imports, CLI entrypoints, SQL writes and process calls are in `audit_evidence/static_inventory.json` and `audit_evidence/STATIC_ENTRYPOINT_WRITER_INDEX.md`. Candidate indexes include false positives. Dynamic imports, external scheduler registrations and live process state cannot be exhaustively established from the copy alone.

## 隔离结果 / Isolation result

| 对象 / Object | 开发处理 / Development handling |
|---|---|
| `.env` | 原件仅保留为 `_audit_quarantine/.env.production-disabled`；根 `.env` 为无生产凭据的审计配置。 / Original retained under quarantine; root file contains audit-only settings without production credentials. |
| `data/bd_leads.db` | 改名为 `data/bd_leads_dev_snapshot.db`，只读属性；审计以 `mode=ro&immutable=1` 和 `query_only=ON` 打开。 / Renamed, read-only attribute, opened using read-only immutable URI and query-only connection. |
| `output`, `logs`, `.workbuddy`, `.wrangler`, caches | 移至 `_audit_quarantine`；嵌套缓存移至其 `nested_runtime`。旧 PID、锁、状态、缓存不得解释为开发运行状态。 / Quarantined, including nested runtime caches. Old PIDs, locks, status and caches are not development runtime state. |
| shell/Windows launchers | `.cmd/.bat/.ps1/.vbs/.sh` 增加 `.audit-disabled` 后缀。 / Launchers receive disabled suffixes. |
| Cloudflare deployment | `cloudflare/wrangler.toml.audit-disabled`，本地登录/运行缓存已隔离。 / Deployment configuration disabled and cached runtime isolated. |
| Python | 新增 `sitecustomize.py` 阻止从此目录普通启动 Python；审计脚本使用 `-I`，仅导入标准库。 / Added accidental-start guard; isolated audit script imports standard library only. |
| 冻结文件 / Frozen files | 五文件保留原内容；SHA-256 见 `audit_evidence/frozen_sha256.json`。 / Five files retain their contents, with SHA-256 manifest. |

中文：上述是本阶段的防误启动措施，不是可安全执行任意旧脚本的沙箱。`-I/-S`、不同工作目录、继承的环境变量、硬编码绝对路径仍可绕过局部配置；原始凭据与历史数据库为完整性保留在副本内，未加密，不能发布此目录。进入运行测试前仍需操作系统级无网络/无生产写权限环境及统一 DB 路径断言。当前只执行标准库审计器，未把开发代码连接到任何调度器。

English: These are Phase 1 accidental-start controls, not a sandbox for arbitrary legacy execution. `-I/-S`, another working directory, inherited environment and hardcoded paths can bypass local settings. Original credentials and historical databases remain in the copy for completeness and are not encrypted; do not publish this directory. Executable testing requires OS-level network/production-write isolation and uniform DB path assertions. Only the standard-library auditor was executed; no development code was registered with schedulers.

## 主运行链 / Main runtime chain

```text
外部定时触发 / External scheduled trigger
  -> bd_orchestrator.main
     -> inventory: active state -> retail_city_queue
        -> DiscoveryService -> provider -> lead_discovery_results/hits/query_state
        -> staging postprocess -> official pages -> identity/email/evidence
        -> history_crosscheck -> evaluate_a0 -> bd_db.insert_lead -> leads
        -> existing-website recovery -> http_scan_website -> submit_manual_email
     -> pre-send: select_candidates_for_plan_v2
        -> V1 [Broad Ready + ICP + evidence + timezone] + V2 [MX + freshness]
        -> bd_template -> final_send_plan.create_plan
     -> outreach: daily_session.execute_final_send_plan
        -> preflight -> authorization -> recipient window -> bd_sender.send_one
        -> SMTP -> transaction [send_log + FSP + authorization + leads]
     -> post-send / morning / end-of-day -> recovery + reports

BDExecutionHost -> delivery_guard + bd_review_server (Ops Center)
                                      -> embedded bd_ops_poller
                                      -> review_workflow / manual_email_workflow
SMTP/IMAP + Cloudflare Worker/D1 <-> tracking/bounce/reply/suppression recovery
```

中文：`SAFE_FSP` 在此作为业务要求使用，现有代码没有同名独立实现；实际边界是 V2 选人并向 `create_plan(... eligible_check=campaign_eligible_check_v2(conn))` 注入校验。V2 内含 MX 校验，不是一个可以绕过 V2 后单独补验的步骤。40/day、收件人时间窗和授权规则保持冻结。

English: `SAFE_FSP` describes the requested business contract, not a distinct implementation found in the code. The implemented boundary is V2 selection followed by `create_plan` with an injected V2 eligibility check. MX is part of V2 rather than a later substitute for it. The 40/day quota, recipient window and authorization rules remain frozen.

## 模块与状态 / Modules and state

| 模块 / Module | 责任与状态 / Responsibility and state |
|---|---|
| `bd_orchestrator.py:92,385,737` | 阶段入口、库存和计划编排；写 job/config/lock，调用各子系统。 / Stage entrypoint, inventory/plan orchestration, job/config/lock writes. |
| `discovery/discovery_service.py:109,197,408` | provider 分页、暂存、官网后处理、历史去重、候选入库。 / Provider pagination, staging, website postprocessing, history deduplication and insertion. |
| `discovery/providers/*` | Google Places/SerpAPI、Browser Maps、目录、mock；provider 能力不等价。 / Providers with unequal capabilities. |
| `inventory_monitor_executor.py:305,590` | 共享 HTTP 扫描器及另一个独立库存 main；后者不是 canonical stage 的同一执行器。 / Shared HTTP scanner plus a separate standalone inventory runner. |
| `broad_ready.py`, `campaign_eligible.py`, `icp_profile.py` | 基础资格、业务适配、历史与证据规则。 / Base qualification, business fit, history and evidence rules. |
| `campaign_eligible_v2.py:215,353` | 加上 MX 明确通过、证据 90 天新鲜度和来源质量；实时 MX 可能联网。 / Adds explicit MX pass, 90-day evidence freshness and source quality; MX can contact network. |
| `final_send_plan.py:45` | 冻结计划；新计划创建前取消同 message_type 的旧 planned 行。 / Freeze plans; cancel older planned rows of same message type. |
| `daily_session.py:72`, `bd_sender.py:498` | 消费计划、授权、预检、时区与 SMTP；不可因补库不足放宽。 / Consume plans with authorization, preflight, timezone and SMTP safeguards. |
| `bd_db.py`, `history_crosscheck.py` | SQLite 权威写入封装与去重；get_db 本身设置 WAL。 / SQLite persistence and identity history; get_db sets WAL. |
| `bounce_pipeline.py`, `result_recovery_sync.py`, `post_send_reconciliation.py` | IMAP/跟踪回流、抑制与对账，部分标为报告的操作实际写库。 / IMAP/tracking recovery, suppression and reconciliation; some reporting operations write state. |
| `bd_review_server.py`, `bd_ops_api.py`, `bd_dashboard_v3.2.py` | Ops Center、审核 API、指标与静态 HTML；启动服务会启动 poller。 / Ops UI, review APIs, metrics and HTML; server startup starts poller. |
| `email_engagement/*`, `cloudflare/src/*` | 本地 tracking 元数据、Worker/D1 打开跟踪；本地 webhook 映射 unsubscribe 事件，不能据此认定 Worker 有退订路由。Plunk POC 是另一种 provider。 / Local tracking metadata and Worker/D1 open tracking; the local webhook maps unsubscribe events, which does not establish a Worker unsubscribe route. Plunk is an alternate POC provider. |
| `facebook_enrichment/*`, `fb_fallback_recovery.py`, `workbuddy_candidate_modules/*` | 辅助富集/候选实现，部分写库或引用其他工作区。 / Auxiliary enrichment and candidate implementations, some with DB writes or external workspace paths. |

## 配置与生产依赖 / Configuration and production dependencies

中文：复制的 `.env` 声明 `DISCOVERY_PROVIDER=browser_maps`、`BROWSER_MAPS_MODE=direct`；快照 active state=NY。`load_provider()` 无参构造 BrowserMapsProvider，而其 mode 默认 `file`，会遮蔽环境变量 direct。运行进程继承环境是否覆盖这些值，本审计没有查询。

English: Copied `.env` declares Browser Maps with direct mode; snapshot active state is NY. `load_provider()` constructs BrowserMapsProvider without arguments, whose nonempty default `file` masks the direct-mode environment setting. Actual inherited process overrides were not inspected.

| 配置 / Configuration | 重复位置或依赖 / Duplicate locations or dependencies |
|---|---|
| DB root | `bd_db.py:16`, `preflight_gate.py:39` 使用环境路径；inventory/poller/review 等有各自默认；`db.py` 使用 `data/leads.db`，`phase1_db.py` 使用另一数据库。 / Environment overrides coexist with independent relative defaults and legacy databases. |
| quota/target | `outreach_control.py` 新外联 40、工作日库存 30、周末 60；service 镜像 40；`env_loader.py` 默认 daily 30；system_config 40；独立 inventory 固定 30。 / Divergent mirrored quotas and inventory targets. |
| time | 编排上海 23 点、recipient_scheduler 本地 08:00–11:10（代码秒边界见实现）；SQLite job timestamps 为 UTC；旧 docstring 仍写上午。 / Shanghai orchestration, recipient local window, UTC job storage and stale morning docstrings coexist. |
| evidence/state | canonical discovery 读取 active state=NY；A0 hygiene 仍限 TN/AR/KY 零售；V2 有更广泛业务判定。 / NY discovery conflicts with tri-state retail A0 promotion. |
| process | Windows pywin32、服务宿主、Task Scheduler、电源 API、WorkBuddy Python/Node 路径、系统代理。 / Windows service/scheduler/power APIs and machine-specific runtimes/proxy. |
| network | Playwright/Chromium、httpx、urllib、curl、Google/SerpAPI 可选密钥、腾讯 Exmail SMTP/IMAP、Cloudflare Worker/D1/Wrangler。 / Browser, HTTP, search APIs, email and Cloudflare dependencies. |
| packaging | 副本中未找到 requirements/pyproject/package.json/锁文件。 / No dependency manifest or lockfile found in the copied tree. |

## 数据快照 / Database snapshot

中文：1,069 leads；418 缺官网，483 缺邮箱，99 有官网无邮箱（全库统计，非可发资格统计）。480 待人工审核，其中 257 为 website_lookup_required。312 discovery results 中 296 缺 website。send_log=516，其中 sent=513、failed=3；不等于 513 家唯一商户，也不代表送达 513。最近 9 月 7 日库存 33/30 完成，pre-send 0/40，outreach 缺计划停止。详细统计见 `audit_evidence/snapshot_summary.json`。

English: 1,069 leads; 418 lack websites, 483 lack email, and 99 have websites but no email (whole-table counts, not send eligibility). Of 480 manual-review leads, 257 require website lookup. Of 312 discovery results, 296 lack websites. There are 516 send-log rows: 513 sent and 3 failed, not necessarily 513 unique merchants or deliveries. September 7 inventory completed at 33/30, pre-send produced 0/40 and outreach stopped without a plan. Detailed counts are in the snapshot evidence file.

中文：更正历史判断：`bd_db.start_job_run:923` 用 `datetime('now')` 写 UTC。09-07 的 07:01 对应上海 15:01，14:30 对应 22:30。旧 P2.4D 报告把 07:xx 当成本地上午，据此判定库存漏触发并不可靠。报告的完整周期失败仍有其他依据，但“库存没运行”不能照抄；本次也没有重验该历史窗口。

English: Correction to the historical interpretation: `start_job_run` stores UTC using SQLite `datetime('now')`. 07:01 on September 7 is 15:01 Shanghai, and 14:30 is 22:30. The old P2.4D report's interpretation of 07:xx as local morning does not reliably establish a missed inventory trigger. Other evidence may still support cycle failure, but the missing-inventory claim must not be repeated without revalidation.
