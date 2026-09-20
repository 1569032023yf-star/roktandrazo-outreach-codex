# PHASE 4A.7B — 城市耗尽语义定稿 / City Exhaustion Semantics Finalization

## 范围与安全 / Scope and safety

本阶段仅在开发仓库中修改 `retail_city_queue.py` 与其测试；没有修改 DiscoveryService、数据库 schema、V2、MX、enrichment、模板或发送链。新的生产数据库只读 SQLite online-backup 副本通过 `PRAGMA integrity_check = ok`；所有重放写入均在副本事务内 rollback。

This phase changed only `retail_city_queue.py` and its tests in the development repository. DiscoveryService, database schema, V2, MX, enrichment, templates, and the send chain were not changed. A fresh read-only production SQLite online-backup copy passed `PRAGMA integrity_check = ok`; every replay write was rolled back within the copy transaction.

PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
PRODUCTION_INVENTORY_RUNS = 0
SMTP = 0
IMAP = 0
SCHEDULER_CHANGES = 0
FROZEN_FILES_CHANGED = 0

## 先追溯真实契约 / Provenance before interpretation

`two_empty_pages` 与 `last_three_batches_empty` 最初仅作为 `all_city_completion_conditions_met()` 的必需 Boolean 键出现在基线提交 `5d432ba`。仓库历史、迁移、测试和交接文档均未定义独立的、可持久化的城市级“三批”进度度量。

`two_empty_pages` and `last_three_batches_empty` originated only as required Boolean keys in `all_city_completion_conditions_met()` in baseline commit `5d432ba`. Repository history, migrations, tests, and handoff documents do not define an independent durable city-level three-batch progress measurement.

可验证的既有 Discovery 契约是：`provider_request_audit.result_count` 等于页面原始 `len(page.results)`；而 `new_unique_places`、`duplicate_places` 与 `consecutive_pages_without_new_place` 才是持久化的唯一性进度。查询会在“没有下一页 cursor”或“连续两页新增唯一商户为零”时写为 `completed`，并清空 cursor、写入 `completed_at`。

The verifiable existing Discovery contract is: `provider_request_audit.result_count` equals raw `len(page.results)`, while `new_unique_places`, `duplicate_places`, and `consecutive_pages_without_new_place` persist uniqueness progress. A query becomes `completed` when it has no next-page cursor or two consecutive pages with zero new unique places; its cursor is cleared and `completed_at` is written.

所以 `raw=20/new_unique=0/duplicates=20` 是合法重复耗尽，不能要求原始结果数为零。因没有持久化的城市级三批新增进度，`last_three_batches_empty` 保留为兼容性门槛，但映射到该可验证的查询耗尽契约；它不声称实际测量了三个城市批次。

Thus `raw=20/new_unique=0/duplicates=20` is valid duplicate exhaustion and raw result count must not be required to be zero. Because no durable city-level three-batch new-progress history exists, `last_three_batches_empty` remains a compatibility gate mapped to the proven query-exhaustion contract; it does not claim to measure three city batches.

## 窄修正 / Narrow correction

查询耗尽现在失败关闭地要求：恰有全部 20 个零售查询族、每个状态为 `completed`、cursor 为空、存在 `completed_at`，且 `pages_processed > 0`。它不读取或解释原始 `result_count` 作为新增唯一性指标。

Query exhaustion now fails closed by requiring exactly all 20 retail query families, each `completed`, with an empty cursor, `completed_at`, and `pages_processed > 0`. It does not read or interpret raw `result_count` as a new-uniqueness metric.

保留 4A.7A 的 manual-review 区分：只有既有 linked-backlog 流程真正可重试的记录阻止城市推进；终结型人工审核不再永久钉住队列。网络重试、未处理 staging 与 linked-backlog 重试仍会阻止推进。

The Phase 4A.7A manual-review distinction remains: only rows genuinely retryable by the existing linked-backlog flow block advancement; terminal manual classifications no longer pin the queue indefinitely. Network retries, unprocessed staging, and linked-backlog retries still block advancement.

DB_MIGRATION_REQUIRED = false
SOURCE_FILES_CHANGED = retail_city_queue.py
TEST_FILES_CHANGED = tests/test_phase4a7_city_queue_advancement.py

## 当前 Ithaca 只读审计 / Current Ithaca read-only audit

| 指标 / Metric | 结果 / Result |
|---|---:|
| BrowserMaps 查询总数 / query total | 20 |
| 已完成 / completed | 10 |
| 待处理查询族 / pending query families | 10 |
| `manual_review_needed` | 13 |
| 其中可重试 / retryable among those | 1 |
| 其中终结型 / terminal-classified among those | 12 |
| 可重试网络记录 / retryable network rows | 1 |
| 未处理 staging / unprocessed staging rows | 5 |
| linked backlog 重试 / linked-backlog retry rows | 8 |

结论：当前 Ithaca 正确保持 `active`，没有提前推进。

Conclusion: current Ithaca correctly remains `active`; there is no premature advancement.

## 生产副本确定性重放 / Production-copy deterministic replay

所有场景在本地副本单一事务内构造并 rollback：

| 验收场景 / Acceptance scenario | 结果 / Result |
|---|---|
| 原始当前 Ithaca / original current Ithaca | 所有完成条件 false / all completion conditions false |
| 重复耗尽页 / duplicate exhaustion page | `raw_result_count=20`，查询完成条件 true / query completion true |
| 终结型 manual review / terminal manual review | 可完成并终结 / can complete and terminalize |
| 下一 NY 城市 / next NY city | Saratoga Springs |
| 注入 `network_retry` / injected `network_retry` | 阻止终结 / blocks terminalization |

COPY_TRANSACTION_ROLLED_BACK = true
TERMINAL_MANUAL_REVIEW_DOES_NOT_PIN = true
RETRYABLE_ROWS_BLOCK_ADVANCEMENT = true
DUPLICATE_RAW_20_COMPLETES = true
NO_PREMATURE_CITY_COMPLETION = true
EXHAUSTED_ITHACA_ADVANCES_TO = Saratoga Springs

## 测试与决定 / Tests and decision

TARGETED_TESTS = 26 passed; 0 failed; 0 errors
FULL_PROJECT_UNITTEST = 357 passed; 0 failed; 0 errors

新增回归覆盖合法重复耗尽（`result_count=20/new_unique=0/consecutive=2`）以及缺少持久化 checkpoint 的伪 `completed` 状态必须失败关闭。

New regressions cover valid duplicate exhaustion (`result_count=20/new_unique=0/consecutive=2`) and require a purported `completed` state missing a durable checkpoint to fail closed.

PHASE4A7B_CITY_EXHAUSTION_SEMANTICS_FINALIZED = true
PRODUCTIVE_ITHACA_STAYS_ACTIVE = true
READY_FOR_PRODUCTION = false

下一步为生产评审与另行明确部署授权。本阶段到此停止；不得部署、恢复调度、运行生产 Inventory 或发送。

The next step is production review and separate explicit deployment authorization. Stop here; do not deploy, resume scheduling, run production Inventory, or send.
