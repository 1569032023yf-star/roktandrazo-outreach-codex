# Phase 4A.8B — Linked-backlog finite retry terminal semantics / 已关联积压有限重试终结语义

## Decision / 结论

中文：本阶段仅修正已被当前回放证据证明为终态的 linked-backlog 行。`discovery_id=336` 成功抓取同主体官网、未发现可见公开邮箱或联系表单，因此以既有 `no_public_email` 状态终结，并在既有 JSON 元数据中记录 `terminal_outcome` 与 `terminal_at`。九条 HTTP 403 访问受限记录、一个 timeout 和一个远端断连仍保持重试；它们不证明官网无效、身份不匹配或无公开邮箱，绝不能因历史尝试次数高而错误终结。

English: This phase corrects only linked-backlog rows whose terminal state is proven by current replay evidence. `discovery_id=336` successfully fetched its same-party official site and found neither a visible public email nor a contact form, so it terminalizes through the existing `no_public_email` state and records `terminal_outcome` plus `terminal_at` in existing JSON metadata. Nine HTTP-403 access-blocked rows, one timeout, and one remote disconnect remain retryable; none proves an invalid official site, identity mismatch, or absence of a public email, and high historical attempt counts must not terminalize them.

## Audit and existing convention / 审计与既有约定

中文：对固定 12 条行的代码、Git 历史与生产副本审计未发现已有 retry-cap 或“达到次数即终结”的约定。既有终结状态仅包括 `website_not_found`、`no_public_email` 与 `identity_review`。因此没有引入新的 retry cap、表、列、迁移或城市完成策略。

English: Code, Git history, and the fixed 12-row production-copy audit found no existing retry cap or “attempt-count becomes terminal” convention. Existing terminal states are limited to `website_not_found`, `no_public_email`, and `identity_review`. Therefore this phase adds no retry cap, table, column, migration, or city-completion policy.

## Fixed production-copy audit / 固定生产副本审计

- Source / 来源: authoritative production SQLite opened `mode=ro`, copied with SQLite online backup to a development quarantine path; `PRAGMA integrity_check = ok`.
- Scope / 范围: exactly 12 linked-backlog rows: `291, 292, 294, 336, 356, 362, 369, 392, 393, 395, 404, 407`.
- Safety / 安全: production DB writes `0`; production files changed `0`; SMTP `0`; IMAP `0`; scheduler changes `0`; no production Inventory or deployment.

| Outcome / 结果 | Count / 数量 | Semantics / 语义 |
|---|---:|---|
| `OFFICIAL_SITE_FETCH_OK_NO_EMAIL_NO_FORM` | 1 (`336`) | durable `no_public_email` / 可持久化终结 |
| `OFFICIAL_SITE_FETCH_OK_IDENTITY_MISMATCH` | 0 | no new identity terminal / 无新增身份终结 |
| HTTP 403 access blocked / HTTP 403 访问受限 | 9 | retryable; access denial is not proof of invalid website or no email / 可重试，不是官网无效或无邮箱的证据 |
| `TIMEOUT` | 1 (`369`) | retryable / 可重试 |
| `TRANSIENT_NETWORK_FAILURE` (remote disconnect) | 1 (`407`) | retryable / 可重试 |

中文：真实抓取中 `336` 有四次 HTTP/TLS 成功的同主体页面响应，并无可见邮箱或表单；其余固定路径的 404 不改变该已证明的无邮箱结果。原始 12 条审计明细保留在开发隔离目录且不会提交。

English: In the real fetch, `336` had four HTTP/TLS-successful same-party page responses and no visible email or form; 404 responses from other fixed paths do not invalidate that proven no-email result. The raw 12-row audit detail remains in the development quarantine directory and is not committed.

## Narrow correction / 窄范围修正

中文：只修改 `discovery/discovery_service.py`。linked replay 在成功、已验证官网的“无公开邮箱/表单”路径中保留既有 `no_public_email_or_form` provenance；终结评估器随后只在 `manual_review_needed + official_match=1 + no_public_email_or_form` 时返回 `no_public_email`。同时将已有 `identity_review` 标记为可持久化终态。`official_site_unavailable` 仍不写为终结 provenance，所有 HTTP/TLS/DNS/网络恢复路径保持重试。

English: Only `discovery/discovery_service.py` changed. A linked replay preserves existing `no_public_email_or_form` provenance on the successful, verified-site no-public-email/form path; the terminal evaluator returns `no_public_email` only for `manual_review_needed + official_match=1 + no_public_email_or_form`. Existing `identity_review` is also made durable. `official_site_unavailable` remains non-terminal provenance, keeping all HTTP/TLS/DNS/network recovery paths retryable.

## Fresh-copy deterministic replay / 新鲜副本确定性回放

中文：在新鲜 production online-backup 副本上按已记录的真实公共抓取分类重放全部 12 条，避免重复联网。处理 12 条、后处理 12 条、终结 1 条；`LINKED_RETRY_ROWS_AFTER = 11`。`city_completion_checks(20, "browser_maps")` 的前四项查询/来源检查为 true，但 `all_candidates_classified`、`no_unprocessed_candidates`、`official_site_recheck`、`review_recovery` 为 false；Ithaca 状态仍为 `active`，不会激活 Saratoga Springs。

English: All 12 rows were replayed on a fresh production online-backup copy using the already-recorded real public-fetch classifications, avoiding repeat network traffic. Twelve rows were processed and postprocessed, one terminalized, and `LINKED_RETRY_ROWS_AFTER = 11`. In `city_completion_checks(20, "browser_maps")`, the first four query/source checks are true, while `all_candidates_classified`, `no_unprocessed_candidates`, `official_site_recheck`, and `review_recovery` are false; Ithaca remains `active` and Saratoga Springs is not activated.

## Tests / 测试

- Targeted / 定向: 16 passed, 0 failed, 0 errors (`tests.test_phase4a1b_linked_backlog`, `tests.test_phase4a3_zero_yield`).
- Full standard unittest / 标准完整 unittest: 363 passed, 0 failed, 0 errors.
- Development dependency restoration / 开发依赖恢复: installed only the already-pinned `requirements-dev.txt` dependencies in the development interpreter; the initial missing `tzdata` and `dnspython` errors were environment-only, not a Phase 4A.8B regression.
- Frozen/V2/MX/templates/sender / 冻结链、V2、MX、模板、发送器: no Phase 4A.8B changes; V2 policy changed `false`, MX policy changed `false`.

## Required result fields / 要求结果字段

```text
SOURCE_CHANGES = 1 (discovery/discovery_service.py only)
RETRY_CAP_CONVENTION_FOUND = false
TERMINALIZED_NO_PUBLIC_EMAIL = 1
TERMINALIZED_WEBSITE_NOT_FOUND = 0
TERMINALIZED_IDENTITY = 0
REMAINING_GENUINELY_TRANSIENT = 2
REMAINING_HTTP_ACCESS_BLOCKED_RETRYABLE = 9
LINKED_RETRY_ROWS_BEFORE = 12
LINKED_RETRY_ROWS_AFTER = 11
CITY_COMPLETION_ALL_MET = false
ITHACA_STATUS = active
NEXT_CITY = NOT_ACTIVATED
READY_FOR_PRODUCTION_REVIEW = false
```

中文：唯一阻塞项是 11 条未被证明为终态的 linked-backlog 记录；在不放宽证据规则的前提下，城市不能推进。English: The only blocker is the 11 linked-backlog rows not proven terminal; the city cannot advance without weakening evidence rules.
