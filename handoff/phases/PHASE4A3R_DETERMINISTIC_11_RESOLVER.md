# Phase 4A.3R — Deterministic 11-Row Website Resolver Diagnosis
# Phase 4A.3R — 确定性 11 条官网解析诊断

## Scope / 范围

This development-only phase uses a fresh SQLite online-backup copy of the authoritative production database. It runs `ProviderWebsiteResolver.resolve()` only for the durable cohort below; it does not run Inventory, send email, or write production.

本开发专用阶段使用权威生产数据库的全新 SQLite 在线备份副本。仅对下列固定队列运行 `ProviderWebsiteResolver.resolve()`；不运行 Inventory、不发送邮件、不写入生产环境。

`COHORT_SIZE = 11`
`COHORT_MANIFEST_CREATED = true`
`PRODUCTION_DB_WRITES = 0`
`REAL_SMTP_CONNECTIONS = 0`
`REAL_IMAP_CONNECTIONS = 0`

## Durable acceptance cohort / 持久化验收队列

Created before any resolver network request. Source URL presence is derived from the copied row's provider payload only; no URL or secret is reported.

在任何解析器联网请求之前创建。来源 URL 存在性仅来自副本行的 provider payload；报告不包含 URL 或任何密钥。

| DISCOVERY_ID | LINKED_LEAD_ID | BUSINESS_NAME | CITY | STATE | WEBSITE_PRESENT | SOURCE_URL_PRESENT |
|---:|---:|---|---|---|---|---|
| 309 | 1102 | The Entertainment Zone Arcade | Ithaca | NY | false | false |
| 283 | 1080 | Autumn Leaves Used Books | Ithaca | NY | false | false |
| 284 | 1081 | One Green Horse | Ithaca | NY | false | false |
| 287 | 1083 | Kleins Archery | Ithaca | NY | false | false |
| 290 | 1084 | Found in Ithaca | Ithaca | NY | false | false |
| 295 | 1086 | Gourdlandia | Ithaca | NY | false | false |
| 297 | 1087 | Midas Menagerie | Ithaca | NY | false | false |
| 298 | 1088 | Young’s Gold Silver Coins & Antiquities | Ithaca | NY | false | false |
| 299 | 1089 | Sundrees | Ithaca | NY | false | false |
| 301 | 1090 | Finger Lakes Running | Ithaca | NY | false | false |
| 302 | 1091 | The Treasure Chest Ithaca | Ithaca | NY | false | false |

## Pending runtime diagnosis / 待完成的运行时诊断

The exact cohort above will be measured without Inventory. Results, root-cause evidence, any narrowly justified patch, known-positive controls, process cleanup, and final decision will be appended here.

将不运行 Inventory，只测量上述固定队列。运行结果、根因证据、任何范围内且有依据的补丁、已知正向对照、进程清理和最终决定都会补充于此。

## Resolver measurement / 解析器测量

The existing `ProviderWebsiteResolver.resolve()` ran once per manifest row with its unchanged 45-second boundary. No Inventory stage was called. Error details below are truncated and credential-safe.

现有 `ProviderWebsiteResolver.resolve()` 对清单中每行仅运行一次，45 秒边界保持不变。未调用任何 Inventory 阶段。下列错误细节已截断且不含凭据。

| DISCOVERY_ID | RESULT | ERROR_CLASS | ERROR_DETAIL_SAFE | ELAPSED_MS |
|---:|---|---|---|---:|
| 309 | network_retry | PLAYWRIGHT_ERROR | `Page.goto: net::ERR_NETWORK_CHANGED` | 9062 |
| 283 | network_retry | MAPS_NAVIGATION_TIMEOUT | `Page.goto: Timeout 30000ms exceeded` | 30701 |
| 284 | network_retry | PROVIDER_TIMEOUT | `provider_timeout:45015ms` | 45021 |
| 287 | not_found | NOT_FOUND | — | 44873 |
| 290 | not_found | NOT_FOUND | — | 44855 |
| 295 | network_retry | PROVIDER_TIMEOUT | `provider_timeout:45017ms` | 45023 |
| 297 | network_retry | PROVIDER_TIMEOUT | `provider_timeout:45014ms` | 45021 |
| 298 | not_found | NOT_FOUND | — | 44836 |
| 299 | network_retry | PROVIDER_TIMEOUT | `provider_timeout:45008ms` | 45015 |
| 301 | not_found | NOT_FOUND | — | 44956 |
| 302 | not_found | NOT_FOUND | — | 44966 |

`ATTEMPTS = 11`
`RESOLVED = 0`
`PROVIDER_TIMEOUT = 4`
`MAPS_NAVIGATION_TIMEOUT = 1`
`SOCKET_NOT_CONNECTED = 0`
`PLAYWRIGHT_ERROR = 1`
`NO_PROVIDER_RESULT = 0`
`NOT_FOUND = 5`
`IDENTITY_REVIEW = 0`
`OTHER = 0`

## Three-row timing evidence / 三条计时证据

The observer wraps the existing BrowserMaps resolver provider path in memory only. It does not alter source code or policy. A zero candidate count means the path did not begin any detail-page fanout.

观察器仅在内存中包装现有 BrowserMaps resolver provider 路径；不修改源码或策略。候选数为零表示路径没有开始任何详情页扇出。

| DISCOVERY_ID | SEARCH_NAVIGATION_MS | CARD_COLLECTION_MS | CANDIDATE_COUNT | DETAIL_VISITS_STARTED / COMPLETED | DETAIL_VISIT_ELAPSED_MS | TOTAL_MS | OBSERVATION |
|---:|---:|---:|---:|---:|---|---:|---|
| 283 | 1998 | 3 | 0 | 0 / 0 | [] | 44667 | BrowserMaps returned `ok` with zero cards/results |
| 284 | not captured | not captured | 0 | 0 / 0 | [] | 45018 parent | Child reached the unchanged 45-second boundary before reporting |
| 287 | 2057 | 3 | 0 | 0 / 0 | [] | 44684 | BrowserMaps returned `ok` with zero cards/results |

`FAILURE_BEFORE_CANDIDATES = true` for 283 and 287.
`FAILURE_DURING_DETAIL_FANOUT = false` for all three representatives.
`DETAIL_FANOUT_IS_MEASURED_PRIMARY_CAUSE = false`.

## Root cause and patch decision / 根因与补丁决定

`ROOT_CAUSE_NETWORK_RETRY = SEARCH_TRANSPORT_FAILURE (with zero-card response and one bounded child non-return); not detail fanout.`

实测显示问题发生在搜索传输/返回层：有零候选卡的 `ok` 返回、导航超时、`ERR_NETWORK_CHANGED`，以及一条达到父级边界仍无结果。详情页从未启动，因此不满足“详情页扇出截止时间”为主要根因的证据门槛。

No source patch was justified or made. In particular, the 45-second deadline was not increased and no two-stage path was added.

没有补丁获得实测依据，也未修改源码。特别是：未提高 45 秒上限，未添加两阶段路径。

`BEFORE_RESOLVED = 0`
`BEFORE_NETWORK_RETRY = 6`
`AFTER_RESOLVED = NOT_RUN_NO_JUSTIFIED_FIX`
`AFTER_NETWORK_RETRY = NOT_RUN_NO_JUSTIFIED_FIX`
`AFTER_NOT_FOUND = NOT_RUN_NO_JUSTIFIED_FIX`
`AFTER_IDENTITY_REVIEW = NOT_RUN_NO_JUSTIFIED_FIX`
`NETWORK_RETRY_MATERIALLY_REDUCED = false`

## Known-positive controls / 已知正向对照

Expected domains were read from pre-existing official evidence in the development copy and retained only for post-run comparison; they were never supplied to the resolver.

预期域名从开发副本中既有的官方证据读取，仅用于运行后比对；从未传给解析器。

| CONTROL_ID | EXPECTED_DOMAIN | RESOLVED_DOMAIN | RESULT | ELAPSED_MS | MATCH_EXPECTED | WRONG_DOMAIN |
|---:|---|---|---|---:|---|---|
| 10 | piccolomondotoys.com | piccolomondotoys.com | resolved | 36827 | true | false |
| 17 | greatescapeadventures.net | — | network_retry | 11204 | false | false |
| 27 | thinkertoys.com | — | not_found | 44857 | false | false |

`KNOWN_POSITIVE_EXPECTED_DOMAIN_MATCHES = 1`
`KNOWN_POSITIVE_WRONG_DOMAIN_MATCHES = 0`

## Lifecycle, testing, and safety / 生命周期、测试与安全

All eleven rows were invoked in sequence and records after failures were present, so `NEXT_LEAD_AFTER_FAILURE_RUNS = true`. The resolver's existing Windows Job Object closes its child process tree at every call. System-wide browser process counts are intentionally not used because they include unrelated desktop processes; resolver-owned orphan counts are `0` by the Job Object lifecycle guarantee and completed parent processes.

11 条均按顺序调用，失败后仍有后续记录，因此 `NEXT_LEAD_AFTER_FAILURE_RUNS = true`。现有 resolver 的 Windows Job Object 在每次调用结束时关闭其子进程树。系统范围浏览器进程包含无关桌面进程，故不把全局数量误作本次遗留；基于 Job Object 生命周期保障及所有父进程已结束，resolver 所属孤儿进程为 0。

`ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0 (resolver-owned)`
`ORPHAN_CHROMIUM_PROCESS_COUNT = 0 (resolver-owned)`
`TARGETED_TESTS = NOT_RUN_NO_SOURCE_CHANGE (an attempted global-Python pytest invocation found no pytest module)`
`FULL_SUITE = NOT_RUN_NO_SOURCE_CHANGE; previous verified baseline: 354 passed + 76 subtests`
`FAILED = NOT_APPLICABLE`
`ERRORS = NOT_APPLICABLE`
`V2_POLICY_CHANGED = false`
`MX_POLICY_CHANGED = false`
`PRODUCTION_FILES_IN_PATCH = []`
`FROZEN_FILES_CHANGED = 0`
`PRODUCTION_DB_WRITES = 0`
`REAL_SMTP_CONNECTIONS = 0`
`REAL_IMAP_CONNECTIONS = 0`
`SCHEDULER_CHANGES = 0`

## Decision / 决定

`WEBSITE_RESOLUTION_BLOCKER_FIXED = false`
`READY_FOR_ONE_FINAL_INVENTORY_AFTER_FIX = false`

The real remaining blocker is BrowserMaps search transport/zero-card yield. A detail-fanout patch would not address this measured failure and is therefore outside the authorized condition for a code change. Stop: do not run Inventory or deploy.

真实剩余阻塞项是 BrowserMaps 搜索传输/零候选卡产出。详情页扇出补丁无法解决该实测故障，因此不满足本阶段代码变更的授权条件。停止：不得运行 Inventory 或部署。
