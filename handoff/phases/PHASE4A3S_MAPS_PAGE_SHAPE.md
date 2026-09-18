# Phase 4A.3S — Maps Page Shape / Google Maps 页面形态

## Result / 结果

`SEARCH_PAGE_SHAPE_BUG_CONFIRMED = true` — all 11 fixed-cohort searches rendered an already-loaded merchant panel (title, authority link, address and phone) while returning zero result articles/feed. The prior list-only path waited for articles and empty-scrolled, causing the measured 44–45 second delay. / 11 条固定清单均已渲染商户详情面板（标题、官网链接、地址、电话），但结果卡/feed 为零；此前仅列表路径会等待并空滚动，导致 44–45 秒延迟。

The narrow scraper direct-panel short circuit returns one candidate. Existing resolver identity scoring and minimum score 80 remain unchanged. Ambiguous pages without a concrete title plus identity field still return no candidate and do not become terminal `not_found`. / 窄范围 scraper 直接面板短路返回一个候选；既有 resolver 身份评分与最低 80 分门槛未变。没有具体标题加身份字段的模糊页面仍不返回候选，不会变成终态 `not_found`。

## Fixed deterministic cohort / 修复后固定队列

`BEFORE_RESOLVED = 0`; `BEFORE_NETWORK_RETRY = 6`; `BEFORE_NOT_FOUND = 5`  
`AFTER_RESOLVED = 2`; `AFTER_NETWORK_RETRY = 0`; `AFTER_NOT_FOUND = 9`; `AFTER_IDENTITY_REVIEW = 0`  
`DIRECT_PLACE_SHORT_CIRCUIT_USED = 11`  
`AMBIGUOUS_ZERO_CARD_NOT_FOUND_COUNT = 0`

## Controls and lifecycle / 对照与生命周期

Controls 10, 17 and 27 completed after the fix: expected-domain matches = 1; wrong-domain matches = 0. Controls that did not meet existing identity/evidence conditions remained `identity_review` or `not_found`; none was accepted as a wrong domain. / 修复后完成 10、17、27 三个对照：正确域名匹配 1，错误域名匹配 0；不满足既有身份/证据条件的对照保持 `identity_review` 或 `not_found`，没有错误域名被接受。

`NEXT_LEAD_AFTER_FAILURE_RUNS = true`  
`ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0 (resolver-owned Job Object cleanup)`  
`ORPHAN_CHROMIUM_PROCESS_COUNT = 0 (resolver-owned Job Object cleanup)`

## Tests / 测试

`TEST_RUNNER_USED = .venv\\Scripts\\python.exe -X utf8 -m unittest discover -s tests`  
`TEST_COUNT = 336`  
`FAILED = 0`  
`ERRORS = 0`

Targeted direct-panel and lifecycle tests: 4 passed. / 直接面板与生命周期定向测试：4 项通过。

## Safety and decision / 安全与决定

`V2_POLICY_CHANGED = false`; `MX_POLICY_CHANGED = false`; `FROZEN_FILES_CHANGED = 0`; `PRODUCTION_DB_WRITES = 0`; `REAL_SMTP_CONNECTIONS = 0`; `REAL_IMAP_CONNECTIONS = 0`; `INVENTORY_RUNS = 0`; `DEPLOYMENTS = 0`.

`WEBSITE_RESOLUTION_BLOCKER_FIXED = true`  
`READY_FOR_ONE_FINAL_INVENTORY_AFTER_FIX = true`
