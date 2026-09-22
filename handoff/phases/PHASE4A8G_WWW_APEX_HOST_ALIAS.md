# Phase 4A.8G — Same-party www/apex host-alias probe / 同主体 www/apex 主机别名探测

## Scope and safety / 范围与安全

Only `discovery/discovery_service.py` and development tests changed. A new SQLite online backup of the authoritative production DB passed `PRAGMA integrity_check=ok`; all replay writes were confined to that development copy. The replay used only canonical `run_linked_backlog(..., fetcher=None, staging_ids=[362])`, did not use Maps resolution, and did not run Inventory.

仅修改了 `discovery/discovery_service.py` 和开发测试。权威生产数据库的新鲜 SQLite 在线备份通过 `PRAGMA integrity_check=ok`；所有重放写入仅限该开发副本。重放仅使用标准 `run_linked_backlog(..., fetcher=None, staging_ids=[362])`，未使用 Maps 解析，也未运行 Inventory。

`PRODUCTION_DB_WRITES = 0`; `PRODUCTION_FILES_CHANGED = 0`; `SMTP = 0`; `IMAP = 0`; `SCHEDULER_CHANGES = 0`; `DB_SCHEMA_CHANGES = 0`; `FROZEN_FILES_CHANGED = 0`.

`PRODUCTION_DB_WRITES = 0`；`PRODUCTION_FILES_CHANGED = 0`；`SMTP = 0`；`IMAP = 0`；`SCHEDULER_CHANGES = 0`；`DB_SCHEMA_CHANGES = 0`；`FROZEN_FILES_CHANGED = 0`。

## Host-alias semantics / 主机别名语义

Only a host beginning with `www.` gains one alias candidate: the exact same HTTPS scheme, path, and query with that leading `www.` removed. It uses the repository's existing `normalized_domain()` and `_same_party_domain()` semantics. No sibling, unrelated, or manufactured domain can enter the queue.

仅以 `www.` 开头的主机获得一个别名候选：保持相同 HTTPS scheme、路径和查询参数，仅移除前导 `www.`。它使用仓库已有的 `normalized_domain()` 和 `_same_party_domain()` 语义。不会将兄弟域、无关域或构造域放入队列。

For a stored HTTP `www` URL, the order is: HTTPS same host, HTTPS apex alias, original HTTP same host, then bounded existing first-party paths. The list remains capped at 12. A qualifying same-host or apex HTTPS homepage skips both unnecessary alias probing and HTTP downgrade. A failed HTTPS compatibility probe also prevents later access-level fetch failures in the same site budget from falsely terminalizing the row as `access_unreachable`.

对于存储的 HTTP `www` URL，顺序为：HTTPS 同主机、HTTPS apex 别名、原 HTTP 同主机，然后是受限的既有第一方路径。列表仍限制为 12。合格的同主机或 apex HTTPS 首页会跳过不必要的别名探测和 HTTP 降级。失败的 HTTPS 兼容探测还会防止同一站点预算内后续访问级抓取失败错误地将记录终态化为 `access_unreachable`。

## Fixed-row replay / 固定记录重放

| Metric / 指标 | Result / 结果 |
|---|---|
| Stored URL / 存储 URL | `http://www.sciencenter.org` |
| HTTPS www attempted / 已尝试 HTTPS www | `true` |
| HTTPS apex attempted / 已尝试 HTTPS apex | `true` |
| Apex static HTTP status / Apex 静态 HTTP 状态 | HTTP 400 |
| Apex final URL / Apex 最终 URL | none — `HTTPError` before a successful response / 无——成功响应前发生 `HTTPError` |
| Same-party verified / 同主体已验证 | `false` — no qualifying HTTP/TLS-successful page / 无 HTTP/TLS 成功的合格页面 |
| Email found / 找到邮箱 | `false` |
| Contact form found / 找到联系表单 | `false` |
| Evidence created / 创建证据 | `false` |
| Final validation status / 最终验证状态 | `review_recovery` |
| Linked retry before / 重放前 linked retry | `1` |
| Linked retry after / 重放后 linked retry | `1` |

Both canonical HTTPS probes were attempted. The apex static fetch returned HTTP 400 in this development environment, and no qualifying first-party browser/static page was obtained within existing bounds. No email was inserted, guessed, or hardcoded; no evidence was written. The new compatibility-probe state correctly kept this failed alias recovery as retryable instead of manufacturing `access_unreachable`.

两个标准 HTTPS 探测均已执行。此开发环境中 apex 静态抓取返回 HTTP 400，且在既有边界内未获得合格的第一方浏览器/静态页面。没有插入、猜测或硬编码邮箱；没有写入证据。新的兼容探测状态正确将失败的 alias 恢复保留为可重试，而不是伪造 `access_unreachable`。

## City completion / 城市完成状态

`CITY_COMPLETION_ALL_MET = false`. The still-false checks are `all_candidates_classified`, `no_unprocessed_candidates`, `official_site_recheck`, and `review_recovery`. Ithaca remains `active`; `NEXT_CITY = null`; city queue advancement is not verified and was not forced.

`CITY_COMPLETION_ALL_MET = false`。仍为 false 的检查是 `all_candidates_classified`、`no_unprocessed_candidates`、`official_site_recheck` 与 `review_recovery`。Ithaca 保持 `active`；`NEXT_CITY = null`；城市队列推进未获验证，也未被强制执行。

## Regression / 回归

- Targeted: 26 passed, 0 failed, 0 errors. Covers www-to-apex only, path/query preservation, unrelated-host rejection, HTTPS success avoiding HTTP downgrade, budget cap, visible evidence extraction, and no merchant special case. / 定向：26 项通过，0 失败，0 错误。覆盖仅 www-to-apex、路径/查询保留、无关主机拒绝、HTTPS 成功避免 HTTP 降级、预算上限、可见证据提取及无商户特例。
- Full standard project unittest: 421 passed, 0 failed, 0 errors. / 项目标准完整 unittest：421 项通过，0 失败，0 错误。
- Replay-owned Playwright/Chromium remnants after completion: 0. / 重放完成后本次 Playwright/Chromium 残留：0。

## Decision / 决策

`WWW_APEX_ALIAS_FIXED = true`, but `READY_FOR_PRODUCTION_REVIEW = false`. The remaining factual blocker is environmental reachability: both same-party HTTPS endpoints returned static HTTP 400 and no bounded browser render produced a qualifying page. No rule was weakened and no further source change was made.

`WWW_APEX_ALIAS_FIXED = true`，但 `READY_FOR_PRODUCTION_REVIEW = false`。剩余真实阻塞是环境可达性：两个同主体 HTTPS endpoint 都返回静态 HTTP 400，且没有有界浏览器渲染产生合格页面。未放宽任何规则，也未再修改源码。
