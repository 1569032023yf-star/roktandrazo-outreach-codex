# PHASE 4A.7A — Production-Copy City Completion Semantics Audit / 生产副本城市完成语义审计

## Scope and safety / 范围与安全

中文：从权威生产 `data/bd_leads.db` 使用 SQLite `mode=ro` online backup 创建新鲜隔离开发副本，`PRAGMA integrity_check=ok`。所有统计与 `city_completion_checks()` 均只针对该副本；未运行生产 Inventory、未发送邮件、未连接 SMTP/IMAP，未修改生产文件、生产数据库、V2、MX、补库或模板。

English: A fresh isolated development copy was made from authoritative production `data/bd_leads.db` through SQLite `mode=ro` online backup; `PRAGMA integrity_check=ok`. Every statistic and `city_completion_checks()` call used only that copy. No production Inventory, mail, SMTP/IMAP, production file/database, V2, MX, enrichment, or template change occurred.

## Ithaca measured state / Ithaca 实测状态

| Metric / 指标 | Result / 结果 |
| --- | --- |
| `QUERY_TOTAL` | 20 (BrowserMaps) |
| `QUERY_COMPLETED` | 10 |
| `PENDING_QUERY_FAMILIES` | 10 |
| `MANUAL_REVIEW_NEEDED_DISCOVERY_ROWS` | 13 |
| `OF_THOSE_RETRYABLE` | 1 — existing linked-backlog eligibility / 既有 linked-backlog 资格 |
| `OF_THOSE_TERMINAL_CLASSIFIED` | 12 |
| `RETRYABLE_NETWORK_ROWS` | 1 |
| `UNPROCESSED_STAGING_ROWS` | 5 |
| `LINKED_BACKLOG_RETRY_ROWS` | 8 |
| Current city status / 当前城市状态 | `active` |

中文：Ithaca 仍有 10 个待处理 BrowserMaps 查询，且仍存在可重试网络、staging 和 linked backlog 工作，因此保持 active 是正确的失败关闭结果。

English: Ithaca still has ten pending BrowserMaps query families plus retryable network, staging, and linked-backlog work. Remaining `active` is therefore the correct fail-closed result.

## Risks found and narrow correction / 发现风险与窄修正

### 1. `manual_review_needed` / 人工审核状态

中文：原 4A.7 评估器把全部 13 条 `manual_review_needed` 都作为未处理工作。生产副本审计显示其中仅 1 条通过既有 linked-backlog 自动重试资格；其余 12 条是 hygiene/identity 等终结型人工分类，若全部阻塞会永久钉住城市。

English: The original 4A.7 evaluator treated all 13 `manual_review_needed` rows as open work. The production-copy audit shows only one passes the existing automatic linked-backlog retry eligibility; the other twelve are terminal manual classifications such as hygiene or identity outcomes. Treating all as blockers would pin the city indefinitely.

中文：已仅在现有 4A.7 评估器中修正：未关联且无官网的人工审核记录仍由正常 resolver 阻塞；已关联记录仅在符合既有自动 retry 入口的持久化条件时阻塞。终结型人工审核不再阻塞。未改变 lead、邮箱、证据或 V2。

English: The correction is confined to the existing 4A.7 evaluator: unlinked manual-review rows without a website still block through the normal resolver, while linked rows block only when their durable state matches the existing automatic retry entry gate. Terminal manual classifications no longer block. No lead, email, evidence, or V2 mutation was changed.

### 2. Empty-page and batch semantics / 空页与批次语义

中文：原 `two_empty_pages` 与 `last_three_batches_empty` 都直接别名为 `queries_complete`，这不满足独立语义。副本中 10 个已完成查询的持久化连续无新增页计数分布为 `0:1, 1:1, 2:7, 27:1`；查询完成本身有状态、空 cursor 和完成时间检查，反映真实的持久化查询终结状态。

English: The original `two_empty_pages` and `last_three_batches_empty` both aliased `queries_complete`, so they did not have independent semantics. In the copy, durable consecutive-no-new-page counts for ten completed queries are `0:1, 1:1, 2:7, 27:1`; query completion itself has persisted status, empty cursor, and completion-time evidence, representing actual persisted query termination.

中文：最近三条 `provider_request_audit` 为 `status=ok, result_count=1`，并不证明三批为空。已将 `last_three_batches_empty` 改为独立、保守的持久化条件：最近三条同 provider 审计必须均为 `ok` 且 `result_count=0`。这比“无新增”更严格，但不会把查询完成简单等同于三批为空，因此不会提前推进。

English: The three newest `provider_request_audit` rows are `status=ok, result_count=1`, which does not prove three empty batches. `last_three_batches_empty` is now an independent, conservative durable condition: the latest three same-provider audit records must all be `ok` with `result_count=0`. This is stricter than “no new unique place,” but it never equates query completion with three empty batches and cannot advance prematurely.

## Read-only completion checks / 只读完成检查

```text
all_query_families = false
all_sources_or_reasons = false
pagination_complete = false
two_empty_pages = false
all_candidates_classified = false
no_unprocessed_candidates = false
official_site_recheck = false
review_recovery = false
last_three_batches_empty = false
```

中文：所有键均为 false，且活动城市未被终结；这符合当前生产副本中尚有真实可处理工作的事实。

English: Every key is false and the active city was not terminalized. This matches the real outstanding work in the production copy.

## Validation / 验证

| Validation / 验证项 | Result / 结果 |
| --- | --- |
| City-focused regressions / 城市定向回归 | 25 passed, 0 failed, 0 errors |
| Full project unittest / 完整项目 unittest | 356 passed, 0 failed, 0 errors |
| Terminal manual review does not pin exhausted city / 终结型人工审核不钉住已耗尽城市 | PASS |
| Retryable linked/manual/network work blocks / 可重试 linked/manual/network 工作阻塞推进 | PASS |
| Last-three batch evidence is independent / 最近三批证据独立 | PASS |
| Productive Ithaca stays active / 有产出的 Ithaca 保持 active | PASS |

## Decision / 决策

中文：发现并修正了真实的开发语义问题。当前 Ithaca 不会提前完成；生产部署未获授权，停止等待生产评审与明确部署授权。

English: A real development semantic issue was found and corrected. Current Ithaca cannot complete prematurely. Production deployment is not authorized; stop and await production review plus explicit deployment authorization.
