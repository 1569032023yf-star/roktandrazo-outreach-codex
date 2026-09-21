# Phase 4A.8A — Linked-backlog Drain Validation / 已关联积压排空验证

## Scope and safety / 范围与安全

Chinese: 使用提交 `4c2264205655f716eb4566e5a658a54cc9ca6ad6` 的现有代码。创建了两份生产 `bd_leads.db` 的只读 SQLite online-backup 开发副本；第二份为全新副本，用于替代被本次开发重放进程短暂占用的第一份。两份副本的 `PRAGMA integrity_check` 均为 `ok`。未写生产、未运行生产 Inventory、未调用 SMTP/IMAP、未变更调度、未部署。
English: Existing code at commit `4c2264205655f716eb4566e5a658a54cc9ca6ad6` was used. Two read-only SQLite online-backup development copies of production `bd_leads.db` were created; the second fresh copy replaced the first copy briefly held by this development replay process. `PRAGMA integrity_check` was `ok` for both. No production write, production Inventory, SMTP/IMAP, scheduler change, or deployment occurred.

Chinese: 初次 direct BrowserMaps 重放启动的开发子进程未在既有解析期限内退出，因而仅终止了该次开发进程以释放开发副本锁；没有影响生产进程。最终重放不再启动浏览器，仅读取 Phase 4A.8 已保存的隔离 BrowserMaps provider 事实，并使用相同的 canonical resolver/status 和 linked-backlog 入口。
English: The first direct-BrowserMaps replay child did not exit within the existing resolver bound, so only that development process was terminated to release the development-copy lock; no production process was affected. The final replay did not start a browser: it read the already-recorded isolated Phase 4A.8 BrowserMaps provider fact and used the same canonical resolver/status and linked-backlog entry points.

## Website blocker lane / 官网阻塞队列

- `NOT_FOUND_TERMINALIZED = 7` genuine pre-existing `not_found` rows / 7 条既有真实 `not_found` 行已终结。
- `POISONED_ROW_ID = 374`; cached factual provider page: `status=ok`, `results=1`, `official_websites=0`; `POISONED_ROW_OSERROR = false`; `POISONED_ROW_FINAL_STATUS = website_not_found` / 受污染行使用已有事实缓存，未发生 OSError，最终为 `website_not_found`。
- `OPEN_WEBSITE_LOOKUP_PENDING_AFTER = 0` / 官网查找待处理数为 0。
- The canonical selector observed 10 rows because it also includes eligible manual-review rows; all mutations occurred only in the development copy. The requested seven-count excludes the poisoned eighth row, which is reported separately. / canonical 选择器还观察到 2 条符合条件的人工审核行；所有变更仅在开发副本中。请求的 7 条计数不含单独报告的受污染第 8 条。

## Linked-backlog bounded serial replay / 已关联积压有界串行重放

`LINKED_RETRY_ROWS_BEFORE = 12`; existing `run_linked_backlog(max_results=20)` selected and processed all 12 serially, with its existing per-row savepoint behavior. It called website resolution zero times because every selected row already had an official website, and called staging postprocess 12 times. `terminalized=0`; no row was forced terminal.
`LINKED_RETRY_ROWS_BEFORE = 12`；既有 `run_linked_backlog(max_results=20)` 串行选取并处理了全部 12 条，保留每条既有 savepoint 行为。所有已选行均已有官网，故官网解析调用为 0，staging 后处理调用为 12。终结数为 0；没有强制终结任何行。

| Discovery ID | Before / 前状态 | Resolver / 官网解析 | Postprocess / 后处理 | Terminalized / 已终结 | After / 后状态 |
|---:|---|---|---|---|---|
|291|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|292|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|294|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|336|manual_review_needed|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|manual_review_needed|
|356|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|362|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|369|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|392|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|393|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|395|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|404|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|
|407|review_recovery|not invoked: existing website / 未调用：已有官网|retryable, no status change / 可重试，无状态变化|false|review_recovery|

`LINKED_RETRY_ROWS_AFTER = 12`. This is a truthful remaining blocker: the existing pipeline did not produce a durable terminal outcome for any of these legitimate retry rows. / `LINKED_RETRY_ROWS_AFTER = 12`。这是真实的剩余阻塞：既有流程未为任一合法重试行产生可持久化的终结结果。

## City completion proof / 城市完成证明

| Completion key / 完成键 | Value / 结果 |
|---|---|
|all_query_families|true|
|all_sources_or_reasons|true|
|pagination_complete|true|
|two_empty_pages|true|
|last_three_batches_empty|true|
|all_candidates_classified|false|
|no_unprocessed_candidates|false|
|official_site_recheck|false|
|review_recovery|false|

Chinese: 由于 12 条合法 linked-backlog 行仍可重试，`ALL_MET=false`，`complete_active_city_if_exhausted(...)=false`，Ithaca 继续为 `active`，并且不能激活 Saratoga Springs。门禁保持失败关闭；没有放宽城市完成、V2 或 MX。
English: Because the 12 legitimate linked-backlog rows remain retryable, `ALL_MET=false` and `complete_active_city_if_exhausted(...)=false`. Ithaca remains `active`, and Saratoga Springs cannot be activated. The gate remains fail-closed; no city-completion, V2, or MX rule was relaxed.

## Regression / 回归

- Targeted: `python -X utf8 -m unittest tests.test_phase4a8_website_liveness_cache_hygiene -v` — 5 passed, 0 failed, 0 errors. / 定向测试 5 项通过，失败与错误均为 0。
- Full: `python -X utf8 -m unittest discover -s tests -v` — 362 passed, 0 failed, 0 errors. / 标准全量 unittest 362 项通过，失败与错误均为 0。
- `SOURCE_CHANGES = 0`; `FROZEN_FILES_CHANGED = 0`; `PRODUCTION_DB_WRITES = 0`; `REAL_SMTP_CONNECTIONS = 0`; `REAL_IMAP_CONNECTIONS = 0`. / 无源码、冻结文件、生产写入、SMTP 或 IMAP 变化。

## Decision / 决策

`READY_FOR_PRODUCTION_REVIEW = false`.
Chinese: 4A.8 官网阻塞已按既有语义安全终结，但 12 条 linked-backlog 合法重试仍未排空，因此当前不可宣称 Ithaca 已耗尽或可推进。下一步需先对这些行的具体、可证明终结条件进行窄范围评审；不得部署、恢复调度或发送。
English: The Phase 4A.8 website blockers terminalized safely under existing semantics, but the 12 legitimate linked-backlog retries did not drain. Ithaca therefore cannot be claimed exhausted or advanced. The next action is a narrow review of a provable terminal condition for these rows; do not deploy, resume scheduling, or send.
