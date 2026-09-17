# Phase 4A.3H — Final production-copy lead-factory throughput acceptance / 最终生产副本 Lead Factory 吞吐验收

## Scope and safety / 范围与安全

One and only one canonical Inventory run was completed on a fresh SQLite online-backup copy of the authoritative production database. The source database was opened read-only; all Inventory, MX-cache and job-run writes were confined to the development copy. BrowserMaps ran in `direct` mode with the production-equivalent scraper route `127.0.0.1:3213`. No Google Places fallback or Google API credential was used. / 在权威生产数据库的全新 SQLite 在线备份副本上完成了一次且仅一次标准 Inventory。源数据库仅以只读方式打开；所有 Inventory、MX 缓存和 job-run 写入均限制在开发副本。BrowserMaps 使用 `direct` 模式及生产等价抓取路由 `127.0.0.1:3213`。未回退 Google Places，未使用 Google API 凭据。

`PRAGMA integrity_check = ok`. `BrowserMapsProvider`, Playwright and Chromium were available. `JOB_OBJECT_GUARD_ACTIVE = true`; after the completed run, a narrow read-only process check found `ACTIVE_PLAYWRIGHT_OR_BROWSERMAPS_PROCESS_COUNT = 0`. / `PRAGMA integrity_check = ok`。`BrowserMapsProvider`、Playwright 和 Chromium 均可用。`JOB_OBJECT_GUARD_ACTIVE = true`；运行结束后的窄范围只读进程检查发现 `ACTIVE_PLAYWRIGHT_OR_BROWSERMAPS_PROCESS_COUNT = 0`。

Production changes, production DB writes, SMTP, IMAP, production FSP and production authorization creation were all `0`. No scheduler was resumed. / 生产文件变更、生产数据库写入、SMTP、IMAP、生产 FSP 与生产授权创建均为 `0`。未恢复任何调度。

## Measured baseline and outcome / 实测基线与结果

| Metric / 指标 | Result / 结果 |
|---|---:|
| TOTAL_LEADS | 1069 |
| RETRYABLE_LINKED_BACKLOG | 18 |
| V2_ELIGIBLE_UNSENT_BEFORE | 0 |
| READ_ONLY_SAFE_UNIQUE_ORGS_BEFORE | 0 |
| MATERIALIZED_FSP_PLANNED_BEFORE | 0 |
| ACTIVE_CITY_START → END | Ithaca, NY → Ithaca, NY |
| MAPS_RESULTS_SEEN / NEW_UNIQUE / DUPLICATES | 8 / 0 / 8 |
| QUERY_FAMILIES_COMPLETED / CITY_ADVANCED | 1 / false |
| LINKED_BACKLOG_ELIGIBLE / PROCESSED | 18 / 18 |
| LINKED_BACKLOG_WEBSITE_PROCESSED / POSTPROCESS_PROCESSED | 11 / 7 |
| LINKED_BACKLOG_TERMINALIZED | 9 |
| WEBSITE_RESOLUTION_ATTEMPTS / RESOLVED | 11 / 0 |
| WEBSITE_RESOLUTION_TIMEOUTS / OTHER_RETRY | 6 / 0 |
| WEBSITE_NOT_FOUND | 5 |
| OFFICIAL_EMAILS_FOUND / PERSISTED | 0 / 0 |
| FULL_EVIDENCE_CREATED / EXISTING_LEADS_LINKED | 0 / 0 |
| V2_ELIGIBLE_UNSENT_AFTER | 0 |
| READ_ONLY_SAFE_UNIQUE_ORGS_AFTER / NEW_SAFE_UNIQUE_ORGS | 0 / 0 |
| MATERIALIZED_FSP_PLANNED_AFTER | 0 |

The job completed normally as `partial` with `safe_inventory_gap`, `actual=0`, and `gap=50`; it did not stall the batch after a timeout. Six resolver attempts returned retryable `provider_timeout` at approximately 45.0 seconds (observed range 45012–45028 ms), and subsequent linked rows continued through the same run. The five remaining resolution attempts completed as `website_not_found`. / 作业正常以 `partial` 完成，原因为 `safe_inventory_gap`，`actual=0`、`gap=50`；超时后没有阻塞整个批次。六次 resolver 尝试以约 45.0 秒的可重试 `provider_timeout` 返回（观察范围 45012–45028 ms），后续已关联记录在同一次运行中继续处理。其余五次解析以 `website_not_found` 完成。

The telemetry writer failed only after Inventory had returned, because its local JSON object retained an unserializable set. It did not alter the completed job or database. Therefore p50/p95 across all eleven calls were not captured and are explicitly `NOT_CAPTURED`, rather than inferred. No second Inventory, website run, or MX run was performed. / 遥测写入器只在 Inventory 返回后失败，原因是本地 JSON 对象保留了不可序列化的集合；它没有改变已完成的作业或数据库。因此所有十一次调用的 p50/p95 未被捕获，明确标为 `NOT_CAPTURED`，不作推断。未执行第二次 Inventory、网站运行或 MX 运行。

## Funnel decision / 漏斗决策

`TIMEOUT_STALLS_WHOLE_BATCH = false`. Lifecycle/progression behavior held: all 18 eligible linked records were processed despite six bounded timeouts, and no resolver-owned browser process remained. / `TIMEOUT_STALLS_WHOLE_BATCH = false`。生命周期和推进逻辑符合预期：虽然有六次有界超时，18 条符合条件的已关联记录均被处理，且未留下 resolver 所有的浏览器进程。

`REAL_DOMINANT_FUNNEL_BLOCKER = WEBSITE_RESOLUTION_LOW_SUCCESS`: 0/11 official-site resolutions succeeded; six were retryable timeouts and five were genuine not-found outcomes. Consequently no visible first-party email or full evidence was created, and frozen V2/MX had zero eligible unsent organizations. / `REAL_DOMINANT_FUNNEL_BLOCKER = WEBSITE_RESOLUTION_LOW_SUCCESS`：11 次官网解析中成功数为 0；六次为可重试超时，五次为真实未找到。因此未产生可见第一方邮箱或完整证据，冻结 V2/MX 的未发送合格组织数为 0。

`FSP_40_SIMULATION_PASS = NOT_RUN_BELOW_40`; `FSP_40_UNIQUE_ORGS = 0`; `AUTHORIZATION_PATH_PASS = NOT_RUN_BELOW_40`. This is correct fail-closed behavior, not a policy failure. / `FSP_40_SIMULATION_PASS = NOT_RUN_BELOW_40`；`FSP_40_UNIQUE_ORGS = 0`；`AUTHORIZATION_PATH_PASS = NOT_RUN_BELOW_40`。这是正确的 fail-closed 行为，而非策略失败。

## Release decision / 发布决策

`LEAD_FACTORY_THROUGHPUT_PROVEN = false` and `READY_FOR_CONTROLLED_PRODUCTION_PATCH = false`. The exact blocker is the measured zero official-site resolution yield in this production-parity backlog, not V2/MX relaxation, sending, or a lifecycle orphan. No code was changed in this phase. / `LEAD_FACTORY_THROUGHPUT_PROVEN = false`，`READY_FOR_CONTROLLED_PRODUCTION_PATCH = false`。确切阻塞点是该生产等价积压中实测官网解析产出为零，不是 V2/MX 放宽、发送或生命周期孤儿问题。本阶段未修改代码。

Frozen V2/MX policy changed: `false`. Existing full suite evidence remains `341 passed + 76 subtests; 0 failed, 0 errors`; no source changed after that suite, so no test was rerun solely for this measurement. / 冻结 V2/MX 策略变更：`false`。现有完整套件证据仍为 `341 passed + 76 subtests; 0 failed, 0 errors`；该套件后无源码改动，因此未只为本次测量重跑测试。
