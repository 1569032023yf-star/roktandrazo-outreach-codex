# Phase 4A.8F — Official-site HTTPS-upgrade probe / 官网 HTTPS 升级探测

## Scope and safety / 范围与安全

Only `discovery/discovery_service.py` and its development tests changed. A fresh SQLite online backup of the authoritative production database passed `PRAGMA integrity_check=ok`; it was the only database written during replay. The replay invoked the canonical `run_linked_backlog(..., fetcher=None, staging_ids=[362])` path, used no Maps resolver, and ran no Inventory.

仅修改了 `discovery/discovery_service.py` 及其开发测试。权威生产数据库的新鲜 SQLite 在线备份通过 `PRAGMA integrity_check=ok`；重放期间仅写入该副本。重放调用标准 `run_linked_backlog(..., fetcher=None, staging_ids=[362])` 路径，未使用 Maps resolver，未运行 Inventory。

`PRODUCTION_DB_WRITES = 0`; `PRODUCTION_FILES_CHANGED = 0`; `SMTP = 0`; `IMAP = 0`; `SCHEDULER_CHANGES = 0`; `DB_SCHEMA_CHANGES = 0`; frozen-file changes are `0`.

`PRODUCTION_DB_WRITES = 0`；`PRODUCTION_FILES_CHANGED = 0`；`SMTP = 0`；`IMAP = 0`；`SCHEDULER_CHANGES = 0`；`DB_SCHEMA_CHANGES = 0`；冻结文件变更为 `0`。

## Narrow behavior / 窄范围行为

For an explicitly stored `http://` official URL, `_fixed_first_party_urls()` now puts the same host, path, and query over HTTPS first. The unchanged HTTP URL is retained as a fallback only if the HTTPS homepage has not verified. The entire probe list remains capped at `MAX_FIRST_PARTY_PAGES_PER_SITE = 12`; explicit HTTPS inputs retain their existing ordering.

对于显式存储的 `http://` 官网 URL，`_fixed_first_party_urls()` 现将相同主机、路径和查询参数的 HTTPS URL 放在首位。只有 HTTPS 首页未验证时，才保留原 HTTP URL 作为回退。整个探测列表仍受 `MAX_FIRST_PARTY_PAGES_PER_SITE = 12` 限制；显式 HTTPS 输入保留既有顺序。

The upgraded HTTPS homepage has one narrow browser-compatibility branch for a static HTTP 400. This does **not** classify 400 as `access_unreachable`, does not mark recovery exhaustion when that browser probe fails, and changes neither identity nor evidence/V2/MX policy. There is no Sciencenter-specific code.

升级后的 HTTPS 首页对静态 HTTP 400 有一个窄范围浏览器兼容分支。它**不会**把 400 分类为 `access_unreachable`，浏览器探测失败时也不会标记 recovery exhaustion，并且不改变身份、证据、V2 或 MX 政策。代码中不存在针对 Sciencenter 的特例。

## Fixed-row measurement / 固定记录测量

| Metric / 指标 | Result / 结果 |
|---|---|
| Discovery row / 发现记录 | `362` |
| Stored official website / 存储官网 | `http://www.sciencenter.org` |
| HTTPS upgrade attempted / 已尝试 HTTPS 升级 | `true` (deterministic canonical first probe / 标准首个探测) |
| Static HTTPS result / 静态 HTTPS 结果 | HTTP 400 |
| Browser compatibility result / 浏览器兼容探测结果 | `official_site_browser_page_timeout:12000ms` |
| HTTP success / HTTP 成功 | `false` |
| Same-party verified / 同一主体已验证 | `false` (no qualifying page / 没有合格页面) |
| Email found / 找到邮箱 | `false` |
| Contact form found / 找到联系表单 | `false` |
| Evidence created / 创建证据 | `false` |
| Final validation status / 最终验证状态 | `review_recovery` |
| Linked retry before / 重放前 linked retry | `1` |
| Linked retry after / 重放后 linked retry | `1` |

The visible first-party email was not injected, guessed, or manually inserted. The standard extraction path did not obtain a qualifying HTTP/TLS-successful first-party page under the existing 12-second browser-page deadline, so it correctly persisted no evidence and left the row retryable.

可见第一方邮箱未被注入、猜测或手工写入。在现有 12 秒浏览器页级时限内，标准提取路径没有得到 HTTP/TLS 成功的合格第一方页面，因此正确地没有持久化证据，并保留该记录为可重试。

## City completion / 城市完成状态

`CITY_COMPLETION_ALL_MET = false`. The failed checks are `all_candidates_classified`, `no_unprocessed_candidates`, `official_site_recheck`, and `review_recovery`. Ithaca therefore remains `active`; no completion or next-city activation was attempted.

`CITY_COMPLETION_ALL_MET = false`。未满足的检查为 `all_candidates_classified`、`no_unprocessed_candidates`、`official_site_recheck` 与 `review_recovery`。因此 Ithaca 保持 `active`；未尝试完成城市或激活下一城市。

## Regression / 回归

- Targeted: 21 passed, 0 failed, 0 errors — HTTPS upgrade, first-party evidence, and browser fallback tests. / 定向：21 项通过，0 失败，0 错误——HTTPS 升级、第一方证据与浏览器回退测试。
- Full standard project unittest: 416 passed, 0 failed, 0 errors. / 项目标准完整 unittest：416 项通过，0 失败，0 错误。
- Replay-owned Playwright/Chromium processes after completion: 0. / 重放结束后的本次 Playwright/Chromium 残留进程：0。

## Decision / 决策

`HTTPS_UPGRADE_FIXED = true` as URL-normalization and bounded compatibility semantics. `READY_FOR_PRODUCTION_REVIEW = false`: the factual remaining blocker is not URL normalization, but an HTTP 400 followed by the existing 12-second browser-page timeout on the live environment. This phase explicitly forbade increasing that deadline, so no further source change was made.

URL 规范化和有界兼容语义层面，`HTTPS_UPGRADE_FIXED = true`。`READY_FOR_PRODUCTION_REVIEW = false`：真实剩余阻塞不是 URL 规范化，而是现场环境中 HTTP 400 之后既有 12 秒浏览器页级超时。本阶段明确禁止提高该时限，因此未再修改源码。
