# Phase 4A.3I — Website-resolver yield diagnosis / 网站解析器产出诊断

## Scope and static audit / 范围与静态审计

No full Inventory was run. The investigation used a fresh SQLite online-backup development copy of the authoritative production database (`PRAGMA integrity_check = ok`), three known-positive controls, and only the same eleven 4A.3H resolver cases. Production DB writes, SMTP and IMAP were `0`. / 未运行完整 Inventory。本次调查使用权威生产数据库的全新 SQLite 在线备份开发副本（`PRAGMA integrity_check = ok`）、三个已知正样本控制及仅与 4A.3H 相同的十一条 resolver case。生产数据库写入、SMTP 和 IMAP 均为 `0`。

`ProviderWebsiteResolver.resolve()` calls `provider.search_places(..., page_size=10)`. BrowserMaps direct treats that size as the number of listings to open for detail-page website/address/phone extraction. Thus the current resolver candidate limit and maximum detail visits per resolution are both `10`. Each detail visit may independently use a 15-second navigation timeout, 6-second selector wait and 1-second stabilization delay. Ten detail visits therefore cannot reliably fit the fixed 45-second resolver deadline. / `ProviderWebsiteResolver.resolve()` 调用 `provider.search_places(..., page_size=10)`。BrowserMaps direct 将该大小视为需要打开详情页并提取官网/地址/电话的 listing 数量。因此当前 resolver 候选限制与每次解析最大详情访问数均为 `10`。每次详情访问可独立使用 15 秒导航超时、6 秒选择器等待和 1 秒稳定等待。十次详情访问无法可靠地纳入固定的 45 秒 resolver deadline。

`CURRENT_DESIGN_CAN_RELIABLY_FINISH_WITHIN_45S = false` in the worst case. This static fact did **not** prove that candidate fan-out caused the measured zero yield, so no production source code was changed. / 在最坏情况下，`CURRENT_DESIGN_CAN_RELIABLY_FINISH_WITHIN_45S = false`。这一静态事实**不能**证明候选扇出导致了实测零产出，因此没有修改生产源码。

## Known-positive controls / 已知正样本控制

Controls were selected from existing leads that already had an official website and first-party evidence. Their existing website was used only for comparison, never supplied to the resolver. / 控制样本从已有官网和第一方证据的 lead 中选择。已有官网仅用于比较，从未传给 resolver。

| Limit / 候选限制 | Fully resolved expected domain / 完整解析预期域名 | Retry timeouts / 可重试超时 | P50 ms | Notes / 说明 |
|---:|---:|---:|---:|---|
| 1 | 0/3 | 3/3 | 33345 | two Maps navigation timeouts; one 45s resolver timeout / 两次 Maps 导航超时；一次45秒 resolver 超时 |
| 3 | 0/3 | 2/3 | 45014 | Great Escape returned the expected domain but only at score 60, so correctly `identity_review` / Great Escape 返回预期域名但分数仅60，正确标为 `identity_review` |
| 10 (current) | 1/3 | 1/3 | 40818 | Piccolo Mondo resolved expected domain at score 80 / Piccolo Mondo 以分数80解析到预期域名 |

Per-control details: Piccolo Mondo Toys (ID 10) passed only at limit 10 (`piccolomondotoys.com`, 40818 ms, selected score 80); Great Escape Adventures (ID 17) matched the expected domain at limits 3 and 10 but remained `identity_review` because the best candidate had score 60; Thinker Toys (ID 27) timed out at every limit. / 单项详情：Piccolo Mondo Toys（ID 10）仅在 limit 10 通过（`piccolomondotoys.com`、40818 ms、选中分数80）；Great Escape Adventures（ID 17）在 limit 3 与10均匹配预期域名，但最佳候选分数60，仍正确为 `identity_review`；Thinker Toys（ID 27）在全部限制下超时。

`KNOWN_POSITIVE_CONTROLS_RESOLVE = false`: only one of three completed the unchanged identity policy. The experiment's score-only selection selected limit 10 (1 full success versus 0), but that result is insufficient to establish it as a safe new default. / `KNOWN_POSITIVE_CONTROLS_RESOLVE = false`：三条中仅一条在未变更身份策略下完成。实验的仅分数选择将 limit 10 选为最佳（1 次完整成功，相比 0），但不足以证明它是安全的新默认值。

## Same 4A.3H cohort recheck / 同一 4A.3H cohort 复测

The recheck used the selected limit 10 and exactly eleven eligible no-website linked rows, not an Inventory run. / 复测使用选出的 limit 10，且仅使用十一条符合条件、无官网的已关联记录；不是 Inventory 运行。

| Result / 结果 | Count / 数量 |
|---|---:|
| Attempts / 尝试 | 11 |
| Resolved / 成功解析 | 0 |
| Resolver-deadline timeouts / Resolver 截止超时 | 8 |
| Page-navigation timeout / 页面导航超时 | 1 |
| Other retryable network errors (`ERR_SOCKET_NOT_CONNECTED`) / 其他可重试网络错误 | 2 |
| `website_not_found` / 官网未找到 | 0 |
| `identity_review` / 身份复核 | 0 |

All eleven calls failed before a usable candidate list was produced (`candidate_count = 0`). Therefore none may truthfully be classified as `TARGET_LISTING_FOUND_NO_WEBSITE`, `TARGET_LISTING_NOT_FOUND`, or a genuine `website_not_found`; all are `network_retry` outcomes. The exact 4A.3H cohort did continue after each timeout, so `NEXT_LEAD_AFTER_TIMEOUT_RUNS = true`. / 十一次调用均在生成可用候选列表前失败（`candidate_count = 0`）。因此任何一条都不能如实分类为 `TARGET_LISTING_FOUND_NO_WEBSITE`、`TARGET_LISTING_NOT_FOUND` 或真实 `website_not_found`；全部是 `network_retry`。每次超时后，同一 4A.3H cohort 的后续 lead 均继续处理，因此 `NEXT_LEAD_AFTER_TIMEOUT_RUNS = true`。

## Root cause and decision / 根因与决策

`ROOT_CAUSE_ZERO_WEBSITE_RESOLUTION_YIELD = BROWSERMAPS_DIRECT_TRANSPORT_OR_NAVIGATION_FAILURE_BEFORE_CANDIDATE_COLLECTION`. The controls reproduced Google Maps page navigation timeouts and `ERR_SOCKET_NOT_CONNECTED` even at candidate limit 1, while the cohort yielded zero candidates at the experiment-selected limit 10. The candidate-detail fan-out is a real worst-case deadline-design risk, but it is **not proven as the primary measured zero-yield cause**. / `ROOT_CAUSE_ZERO_WEBSITE_RESOLUTION_YIELD = BROWSERMAPS_DIRECT_TRANSPORT_OR_NAVIGATION_FAILURE_BEFORE_CANDIDATE_COLLECTION`。控制样本即使在 candidate limit 1 也复现了 Google Maps 页面导航超时与 `ERR_SOCKET_NOT_CONNECTED`，cohort 在实验选出的 limit 10 下同样得到零候选。候选详情扇出是真实的最坏情况 deadline 设计风险，但**未被证明是本次实测零产出的主要根因**。

No narrow code fix was authorized by the evidence: changing `discovery/website_resolver.py` to lower the candidate limit would not address the observed pre-candidate transport failure and could remove the only current fully resolved control. `FILES_CHANGED = none`; `PRODUCTION_FILES_IN_PATCH = none`. / 现有证据不支持授权任何窄代码修复：将 `discovery/website_resolver.py` 的候选限制降低无法解决观察到的候选前传输失败，并可能移除当前唯一完整成功的控制。`FILES_CHANGED = none`；`PRODUCTION_FILES_IN_PATCH = none`。

`TIMEOUT_RATE_MATERIALLY_REDUCED = false`; `ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0`; `ORPHAN_CHROMIUM_PROCESS_COUNT = 0`; `READY_FOR_ONE_FINAL_INVENTORY_REHEARSAL = false`. The final Inventory rehearsal must not be run until an explicitly approved fix addresses the transport/navigation failure. / `TIMEOUT_RATE_MATERIALLY_REDUCED = false`；`ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0`；`ORPHAN_CHROMIUM_PROCESS_COUNT = 0`；`READY_FOR_ONE_FINAL_INVENTORY_REHEARSAL = false`。在获得针对传输/导航失败的明确批准修复前，不得运行最终 Inventory 演练。

## Regression / 回归

Targeted lifecycle tests: `2 passed`. Full suite: `341 passed, 76 subtests passed`; `FAILED = 0`, `ERRORS = 0`. No source code changed in this phase. / 定向生命周期测试：`2 passed`。完整套件：`341 passed, 76 subtests passed`；`FAILED = 0`、`ERRORS = 0`。本阶段未修改任何源码。
