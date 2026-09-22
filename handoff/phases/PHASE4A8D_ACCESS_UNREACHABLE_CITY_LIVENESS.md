# PHASE 4A.8D — Access-unreachable recovery deferment / 自动恢复不可达延后

## Scope and safety / 范围与安全

- Development-only implementation and validation from `e449bef79d83e8bac3eca8ed556643b0a0fb31ea`.
- 仅在开发环境实现和验证；生产源码、生产数据库、调度、SMTP、IMAP、Inventory 均未执行或修改。
- Production SQLite was opened read-only and copied with SQLite online backup to an ignored development artifact. `PRAGMA integrity_check = ok`.
- 生产 SQLite 仅以只读方式创建了被忽略的开发副本，完整性检查为 `ok`。
- Network requests during the fixed-cohort replay: `0`; it replayed the already-proven Phase 4A.8C access outcomes.
- 固定队列重放未发起网络请求；仅重放已证明的 4A.8C 访问受限结果。

## Narrow behavior / 窄范围行为

`linked_backlog_retry.automation_terminal_outcome = "access_unreachable"` is persisted only after an allowed static access/transport failure, an eligible browser recovery attempt, and no qualifying same-party HTTP-success page.

该标记仅表示当前获授权的自动恢复传输路径已耗尽；它不是“没有公开邮箱”的事实结论。标记不会写入邮箱、证据、`no_public_email`、FSP 或 V2 状态。运行时 linked-backlog 入口和城市完成评估的持久化镜像都会跳过已标记记录；普通暂态重试仍保持可重试和失败关闭。

Production-candidate source scope / 生产候选源码范围：

- `discovery/discovery_service.py`
- `retail_city_queue.py`

No DB schema change / 无数据库 schema 变更。

## Fixed production-copy replay / 固定生产副本重放

Fixed discovery IDs / 固定 discovery ID：`291, 292, 294, 356, 362, 369, 392, 393, 395, 404, 407`.

| Measure / 指标 | Result / 结果 |
| --- | --- |
| ACCESS_UNREACHABLE_DEFERRED | 11 |
| LINKED_AUTOMATIC_RETRY_ROWS_BEFORE | 11 |
| LINKED_AUTOMATIC_RETRY_ROWS_AFTER | 0 |
| EMAILS_CREATED | 0 |
| EVIDENCE_CREATED | 0 (before 0; after 0) |
| SAFE_GAIN_FROM_DEFERMENT | 0 |
| Cohort lead state / 队列线索状态 | all empty email, `manual_review_needed`, `email_verified_on_official_site=0` / 全部无邮箱、人工复核、官网邮箱验证为 0 |
| Factual terminal outcome / 事实性终结结论 | none / 无 |

Every deferred row retained `validation_status=review_recovery`; no row was labeled `website_not_found`, `no_public_email`, or `identity_review` by this deferment.

每条延后记录均保持 `review_recovery`；本逻辑没有将任何记录标为 `website_not_found`、`no_public_email` 或 `identity_review`。

## City completion result / 城市完成结果

The isolated semantic regression proves that, when deferred rows are the only remaining automatic work, all nine completion checks are true, `complete_active_city_if_exhausted(...)` returns true, Ithaca becomes `search_matrix_exhausted`, and `activate_next_city(state="NY")` selects Saratoga Springs.

隔离语义回归已证明：当延后记录是唯一剩余自动工作时，9 个完成检查全部为真，`complete_active_city_if_exhausted(...)` 返回 true，Ithaca 进入 `search_matrix_exhausted`，且 `activate_next_city(state="NY")` 选择 Saratoga Springs。

The fresh authoritative production snapshot is intentionally pre-deployment and still has separate genuine open work: `website_lookup_pending` IDs `337, 349, 360, 368, 374, 406, 409, 412`, plus normal retryable manual-review ID `336`. Consequently, after replaying only the fixed 11 rows, four city checks remain false, Ithaca remains `active`, and the next active city remains Ithaca. This is the expected fail-closed result, not an access-unreachable marker defect and not a reason to suppress those rows.

新鲜权威生产快照仍处于部署前，另有真实未完成工作：8 条 `website_lookup_pending`（`337, 349, 360, 368, 374, 406, 409, 412`）以及 1 条正常可重试的人工复核记录（`336`）。因此，仅重放固定 11 条后，4 个城市检查仍为 false，Ithaca 仍为 `active`，下一城市仍为 Ithaca。这是预期的失败关闭结果，不是延后标记缺陷，也不能据此压制这些记录。

## Regression / 回归

- Targeted: 67 passed, 0 failed, 0 errors.
- 定向回归：67 项通过，失败 0，错误 0。
- Standard project unittest: 408 passed, 0 failed, 0 errors.
- 标准项目 unittest：408 项通过，失败 0，错误 0。
- Frozen files changed: 0.
- 冻结文件变更：0。

Covered assertions / 覆盖断言：ordinary transient retry remains retryable; static-only failure does not defer; browser recovery success takes normal evidence processing; static-plus-browser access exhaustion defers; deferred rows are not reselected; no email/evidence is invented; only-deferred city work advances; and a newly retryable row blocks advancement.

## Decision / 决策

`READY_FOR_PRODUCTION_REVIEW = true` for the narrow code patch. Production review/deployment must retain the normal Inventory lanes for the nine independent open rows before expecting Ithaca to advance. No production deployment is authorized by this report.

该窄补丁 `READY_FOR_PRODUCTION_REVIEW = true`。在预期 Ithaca 推进前，生产评审/部署必须保留对 9 条独立未完成记录的正常 Inventory 处理路径。本报告不授权生产部署。
