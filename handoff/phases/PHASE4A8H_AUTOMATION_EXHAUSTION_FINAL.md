# PHASE 4A.8H — Automation exhaustion finalization / 自动恢复穷尽最终定稿

## Scope and safety / 范围与安全

This phase used development code and fresh SQLite online-backup copies only.  The authoritative production database was opened read-only as the backup source; its integrity check was `ok`.  No production database or file was written, no Inventory was run in production, and SMTP, IMAP, FSP/authorization creation, deployment, and scheduler changes were all zero.

本阶段只使用开发代码和新鲜 SQLite 在线备份副本。权威生产数据库仅以只读方式作为备份来源，副本 `integrity_check` 为 `ok`。未写入生产数据库或文件，未在生产运行 Inventory，SMTP、IMAP、FSP/授权创建、部署和调度变更均为零。

## Root cause and narrow correction / 根因与窄修正

The canonical browser fallback already records whether a static access failure, a bounded browser compatibility attempt, and a qualifying same-party page occurred.  Its recovery-exhausted predicate incorrectly excluded a failed HTTPS-compatibility probe.  Consequently an explicit HTTP official-site URL that reached static HTTP 400, actually attempted the bounded browser compatibility route, and still produced no qualifying same-party page remained indefinitely retryable.

标准浏览器回退已经记录静态访问失败、有界浏览器兼容尝试和合格同主体页面是否发生。此前 recovery-exhausted 判定错误排除了失败的 HTTPS 兼容性探测。因此，显式 HTTP 官网 URL 遇到静态 HTTP 400、实际执行了有界浏览器兼容路径、仍未得到合格同主体页面时，会无限保持可重试。

Only `discovery/discovery_service.py` changes production behavior.  It now marks an automatic recovery as exhausted only when all of the following are true: a static access failure or HTTPS compatibility probe occurred; the bounded browser route actually ran; and no qualifying same-party page was obtained.  This is generic and contains no merchant, domain, or email special case.

只有 `discovery/discovery_service.py` 改变生产行为。现在仅当以下条件同时满足时，才标记自动恢复已穷尽：发生静态访问失败或 HTTPS 兼容性探测；有界浏览器路径实际运行；且未获得合格同主体页面。该逻辑是通用的，不含商户、域名或邮箱特例。

| Case / 情形 | Result / 结果 |
| --- | --- |
| Plain static HTTP 400, no browser attempt / 仅静态 HTTP 400，未尝试浏览器 | Remains retryable / 保持可重试 |
| HTTP 400 + bounded compatibility browser failure + no qualifying page / HTTP 400 + 有界兼容浏览器失败 + 无合格页面 | Operational recovery exhausted; no factual email/site claim is created / 自动恢复穷尽；不创建事实性邮箱或网站结论 |
| Browser obtains qualifying same-party page / 浏览器获得合格同主体页面 | Normal existing evidence path; no exhaustion marker / 正常既有证据路径；不标记穷尽 |

## Canonical development-copy replay / 标准开发副本回放

The required canonical call was run once on a fresh production-copy database with `run_linked_backlog(city, resolver, max_results=20, fetcher=None)`.  A resolver guard confirmed that this replay did not invoke Maps resolution for rows already holding official websites.

在新鲜生产副本数据库上，按要求仅运行一次标准调用：`run_linked_backlog(city, resolver, max_results=20, fetcher=None)`。解析器保护确认：已持有官网的记录在本次回放中没有调用 Maps 解析。

The supplied expectation of one initial retry was not true for this current authoritative snapshot.  The truthful observed baseline was 11 selectable linked-backlog rows.  The canonical pass selected and processed all 11, deferred 10 with the durable `access_unreachable` automation outcome, and a second identical selection returned zero rows.  No direct status edit or manual terminalization was performed.

用户提供的“初始仅 1 条重试”预期不符合当前权威快照。真实观测基线为 11 条可选择 linked-backlog 记录。标准回放选择并处理了全部 11 条，其中 10 条以持久化 `access_unreachable` 自动结果延后；第二次相同选择返回零记录。未直接编辑状态，也未手工终态化。

- `LINKED_RETRY_ROWS_BEFORE = 11` (observed snapshot / 实际快照)
- `CANONICAL_PROCESSED = 11`
- `AUTOMATION_DEFERRED = 10`
- `LINKED_RETRY_ROWS_AFTER = 0`
- `discovery_id=362` followed the automatic-recovery path; no email or evidence was manually inserted. / `discovery_id=362` 走自动恢复路径；未手工插入邮箱或证据。
- `NEW_EMAILS_CREATED = 0`; `NEW_FULL_EVIDENCE_CREATED = 0`; `SAFE_GAIN = 0`. / 新建邮箱、完整证据与 SAFE 增量均为 0。

## City completion result / 城市完成结果

After the bounded drain, all nine existing `city_completion_checks(20, "browser_maps")` booleans were true:

在有界清空后，现有 `city_completion_checks(20, "browser_maps")` 的九项布尔值全部为真：

`all_query_families`, `all_sources_or_reasons`, `pagination_complete`, `two_empty_pages`, `all_candidates_classified`, `no_unprocessed_candidates`, `official_site_recheck`, `review_recovery`, and `last_three_batches_empty`.

`complete_active_city_if_exhausted(...)` returned `true`; Ithaca became `search_matrix_exhausted`; `activate_next_city(state="NY")` selected `Saratoga Springs`.  This proves city advancement only after no selectable automatic-retry work remains.

`complete_active_city_if_exhausted(...)` 返回 `true`；Ithaca 变为 `search_matrix_exhausted`；`activate_next_city(state="NY")` 选择了 `Saratoga Springs`。这证明仅在没有可选择的自动重试工作后才会推进城市。

## Regression evidence / 回归证据

- Targeted standard unittest: 52 passed, 0 failed, 0 errors. / 定向标准 unittest：52 通过，0 失败，0 错误。
- Full standard unittest: 423 passed, 0 failed, 0 errors. / 完整标准 unittest：423 通过，0 失败，0 错误。
- Frozen send chain changed: 0. / 冻结发送链变更：0。
- `V2_POLICY_CHANGED = false`; `MX_POLICY_CHANGED = false`; no schema migration. / 未修改 V2、MX 策略；无 schema 迁移。

The additional test changes are test-fixture and regression coverage only: one fixture now returns SQLite rows and a concrete provider name, and tests cover both plain HTTP 400 retryability and the bounded compatibility-browser exhaustion outcome.

额外测试改动仅为测试夹具与回归覆盖：一个夹具现在返回 SQLite rows 与确定的 provider 名称；测试同时覆盖“仅 HTTP 400 可重试”和“有界兼容浏览器尝试后穷尽”的结果。

## Production review payload / 生产评审交付物

The cumulative production change since deployed baseline `dc493825` is exactly one file: `discovery/discovery_service.py`.  It includes the approved 4A.8E canonical fetcher-state wiring, 4A.8F HTTPS-first same-host probe, 4A.8G bounded `www`/apex same-party alias probe, and this 4A.8H automatic-recovery exhaustion finalization.  No database migration is required.

自已部署基线 `dc493825` 起，累计生产改动恰好只有一个文件：`discovery/discovery_service.py`。它包含已批准的 4A.8E 标准 fetcher 状态接线、4A.8F HTTPS 优先同主机探测、4A.8G 有界 `www`/apex 同主体别名探测，以及本次 4A.8H 自动恢复穷尽定稿。无需数据库迁移。

## Decision / 决定

`READY_FOR_PRODUCTION_REVIEW = true`.  This is review readiness only; it is not deployment authorization.  Stop after this handoff.  Do not deploy, run production Inventory, resume scheduling, or send.

`READY_FOR_PRODUCTION_REVIEW = true`。这仅表示可进入生产评审，不构成部署授权。交接后停止；不得部署、运行生产 Inventory、恢复调度或发送。
