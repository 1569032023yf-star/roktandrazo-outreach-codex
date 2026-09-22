# PHASE 4A.8C — Official-site browser fallback for access-blocked retries
# Phase 4A.8C —— 访问受限重试的官网浏览器回退

## Scope and safety / 范围与安全

- Development only. A fresh SQLite online-backup copy of the authoritative production database passed `PRAGMA integrity_check = ok`.
- 仅限开发环境。使用权威生产数据库建立新的 SQLite 在线备份副本，`PRAGMA integrity_check = ok`。
- Only the fixed linked-backlog cohort was replayed: `291, 292, 294, 356, 362, 369, 392, 393, 395, 404, 407`. No Inventory, Maps search, SMTP, IMAP, FSP/authorization creation, deployment, production DB write, production-file change, or scheduler change occurred.
- 仅重放固定 linked-backlog 队列：`291, 292, 294, 356, 362, 369, 392, 393, 395, 404, 407`。未运行 Inventory 或 Maps 搜索；未使用 SMTP、IMAP，未创建 FSP/授权，未部署、未写生产数据库、未改生产文件或调度。

## Implementation / 实现

- Changed only production-patch candidate `discovery/discovery_service.py`, plus development tests and handoff files.
- 仅修改生产补丁候选文件 `discovery/discovery_service.py`，以及开发测试和交接文件。
- Existing static fetching remains first. Browser rendering is attempted only after HTTP 401/403, timeout, reset/disconnect, or equivalent retryable transport failure; HTTP 400/503 do not trigger it.
- 既有静态抓取保持优先。仅在 HTTP 401/403、超时、重置/断连或等价可重试传输失败后尝试浏览器渲染；HTTP 400/503 不触发回退。
- The existing same-party, HTTPS-preferred, visible-DOM-only, twelve-page budget, TLS/HTTP, evidence-hash, and no-guessing gates are unchanged.
- 既有同主体、HTTPS 优先、仅可见 DOM、最多十二页、TLS/HTTP、证据哈希和禁止猜测门槛均未改变。
- A browser child is bounded by a per-page timeout and an authoritative per-site deadline. The parent now polls in short intervals and force-terminates the owned child tree at deadline; no unbounded background thread or process is introduced.
- 浏览器子进程受单页时限和权威单站点截止时间约束。父进程现以短间隔轮询，并在到期时强制结束自有子进程树；未引入无界后台线程或进程。

## Fixed manifest before network / 联网前固定清单

| Discovery ID | Static baseline | Retry attempts before | Browser result | Final copy status |
| --- | --- | ---: | --- | --- |
| 291 | HTTP 403 | 64 | Render completed but HTTP 403 on same-party pages | review_recovery |
| 292 | HTTP 403 | 64 | Render completed but HTTP 403 on same-party pages | review_recovery |
| 294 | HTTP 403 | 64 | Browser page/site timeouts | review_recovery |
| 356 | HTTP 403 | 6 | Browser page/site timeouts | review_recovery |
| 362 | HTTP 400 | 12 | Not eligible for fallback | review_recovery |
| 369 | timeout | 10 | Browser page/site timeouts | review_recovery |
| 392 | HTTP 403 | 15 | Browser page/site timeouts | review_recovery |
| 393 | HTTP 403 | 15 | Browser page/site timeouts | review_recovery |
| 395 | HTTP 503 then 403 | 15 | Render completed but HTTP 403 | review_recovery |
| 404 | HTTP 403 | 10 | Render completed but HTTP 403 | review_recovery |
| 407 | remote disconnect | 7 | Timeout or `ERR_EMPTY_RESPONSE` | review_recovery |

中文说明：清单在任何公开官网访问之前写入开发隔离区。浏览器“完成”仅表示浏览器取得响应；HTTP 403 不满足成功 HTTP 证据门槛，不能成为官网邮箱或表单证据。

## Measured result / 实测结果

- `LINKED_RETRY_ROWS_BEFORE = 11`; `LINKED_RETRY_ROWS_AFTER = 11`.
- `LINKED_RETRY_ROWS_BEFORE = 11`；`LINKED_RETRY_ROWS_AFTER = 11`。
- `EMAIL_RECOVERED = 0`; `CONTACT_FORM_RECOVERED = 0`; `TERMINALIZED = 0`; `REMAINING_GENUINELY_UNREACHABLE = 11`.
- `EMAIL_RECOVERED = 0`；`CONTACT_FORM_RECOVERED = 0`；`TERMINALIZED = 0`；`REMAINING_GENUINELY_UNREACHABLE = 11`。
- No returned rendered page met both HTTP-success and the existing same-party identity/evidence requirements. No email, contact form, guessed address, third-party page, hidden/script-only text, or synthetic evidence was promoted.
- 没有任何渲染页面同时满足 HTTP 成功及既有同主体身份/证据要求。没有提升邮箱、联系表单、猜测地址、第三方页面、隐藏/脚本专用文本或合成证据。
- Browser lifecycle was observed across sequential rows: completed child processes exited before later rows launched new children. Final workspace-owned Playwright/Chromium orphan count was `0`.
- 已跨连续行观察浏览器生命周期：已完成子进程在后续行启动新子进程前退出。最终工作区所属 Playwright/Chromium 孤儿进程数为 `0`。

## City completion / 城市完成

`city_completion_checks(20, "browser_maps")` returned:

| Key | Value |
| --- | --- |
| all_query_families | true |
| all_sources_or_reasons | true |
| pagination_complete | true |
| two_empty_pages | true |
| all_candidates_classified | false |
| no_unprocessed_candidates | false |
| official_site_recheck | false |
| review_recovery | false |
| last_three_batches_empty | true |

`CITY_COMPLETION_ALL_MET = false`; `ITHACA_STATUS = active`; `NEXT_CITY = NOT_ACTIVATED`.

中文：`CITY_COMPLETION_ALL_MET = false`；`ITHACA_STATUS = active`；`NEXT_CITY = 未激活`。剩余 11 条诚实的可重试访问/网络失败继续失败关闭地阻止城市推进，没有放宽门槛。

## Tests / 测试

- Targeted browser fallback tests: `8 passed; 0 failed; 0 errors`.
- 定向浏览器回退测试：`8 passed; 0 failed; 0 errors`。
- Standard project command: `python -m unittest discover -s tests -q`.
- 项目标准命令：`python -m unittest discover -s tests -q`。
- Full suite: `371 passed; 0 failed; 0 errors`.
- 完整套件：`371 passed; 0 failed; 0 errors`。
- Coverage includes static-success bypass, HTTP-403 fallback, timeout fallback, expired site deadline, cross-party redirect rejection, hidden-script rejection, visible-email acceptance, successful-render requirement for no-public-email, cleanup, and existing terminal non-reselection regression.
- 覆盖静态成功绕过、HTTP-403 回退、超时回退、站点截止时间、跨主体跳转拒绝、隐藏脚本拒绝、可见邮箱接受、无公开邮箱必须成功渲染、清理，以及既有终态不再重选回归。

## Decision / 决策

`SOURCE_CHANGES = 1` (`discovery/discovery_service.py` only in production scope).

`READY_FOR_PRODUCTION_REVIEW = false`.

The narrow fallback is safe and bounded, but it did not recover a qualifying first-party email/form from this real cohort. The sole remaining blocker is factual access/network unreachability for all 11 rows; they must remain retryable. Do not deploy, resume scheduling, run production Inventory, or send.

中文：窄回退实现安全且有界，但未从这批真实记录中恢复符合条件的第一方邮箱/表单。唯一剩余阻塞是 11 条记录的事实性访问/网络不可达；它们必须保持可重试。不得部署、恢复调度、运行生产 Inventory 或发送。
