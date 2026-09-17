# Phase 4A.3J — Existing Google Maps Place URL Reuse / 复用既有 Google Maps Place URL

## Scope and safety / 范围与安全

- A fresh SQLite online-backup copy of the authoritative production database was created under the development quarantine directory. `PRAGMA integrity_check = ok`. Production was read-only; production database writes, production file changes, SMTP, and IMAP were all `0`. / 在开发隔离目录中通过 SQLite 在线备份创建了权威生产数据库的新副本。`PRAGMA integrity_check = ok`。生产库仅只读；生产数据库写入、生产文件变更、SMTP 与 IMAP 均为 `0`。
- The experiment navigated only stored exact Google Maps Place URLs. It performed no Maps search and no full Inventory run. / 实验仅导航到已存储的精确 Google Maps Place URL；未执行 Maps 搜索，也未运行完整 Inventory。
- All development database copies, browser cache, temporary diagnostic source, and test logs were removed after measurement. / 测量完成后，所有开发数据库副本、浏览器缓存、临时诊断脚本和测试日志均已删除。

## A. Existing `source_url` asset audit / 既有 `source_url` 资产审计

`COHORT_COUNT = 11`

| DISCOVERY_ID | PROVIDER | SOURCE_URL_PRESENT | SOURCE_URL_TYPE | PLACE_ID_PRESENT | PROVIDER_RESULT_ID_PRESENT |
|---:|---|---|---|---|---|
| 309 | browser_maps | true | GOOGLE_MAPS_PLACE | true | true |
| 283 | browser_maps | false | EMPTY | true | true |
| 284 | browser_maps | false | EMPTY | true | true |
| 287 | browser_maps | false | EMPTY | true | true |
| 290 | browser_maps | false | EMPTY | true | true |
| 295 | browser_maps | false | EMPTY | true | true |
| 297 | browser_maps | false | EMPTY | true | true |
| 298 | browser_maps | false | EMPTY | true | true |
| 299 | browser_maps | false | EMPTY | true | true |
| 301 | browser_maps | false | EMPTY | true | true |
| 302 | browser_maps | false | EMPTY | true | true |

- `SOURCE_URL_PRESENT = 1`; `SOURCE_URL_GOOGLE_MAPS_PLACE = 1`; `SOURCE_URL_OTHER = 0`; `EMPTY = 10`. / `SOURCE_URL_PRESENT = 1`；`SOURCE_URL_GOOGLE_MAPS_PLACE = 1`；`SOURCE_URL_OTHER = 0`；`EMPTY = 10`。
- The three Phase 4A.3I known-positive lead controls (`10`, `17`, `27`) had no stored discovery provenance matching their linked or same-merchant discovery record, and therefore had no reusable Place URL. No website was supplied to a resolver. / 三个 Phase 4A.3I 已知正样本 lead 控制项（`10`、`17`、`27`）均没有匹配其关联记录或同商户发现记录的已存储发现来源，因此没有可复用的 Place URL。未向解析器传入任何已知官网。

## B. Provenance confirmation / 来源血缘确认

`SOURCE_URL_IS_ORIGINAL_PROVIDER_ARTIFACT = true` for persisted BrowserMaps values: `extract_place_data_from_card()` reads the listing's `google_maps_url`; `scrape_google_maps()` maps it to `source_url`; `BrowserMapsProvider` maps it to `PlaceSearchResult.source_url`; and `DiscoveryService` inserts it into `lead_discovery_results.source_url`. It is not synthesized. / 对于已持久化的 BrowserMaps 值，`SOURCE_URL_IS_ORIGINAL_PROVIDER_ARTIFACT = true`：`extract_place_data_from_card()` 读取列表的 `google_maps_url`；`scrape_google_maps()` 将其映射为 `source_url`；`BrowserMapsProvider` 映射至 `PlaceSearchResult.source_url`；`DiscoveryService` 插入 `lead_discovery_results.source_url`。该值并非猜测或合成。

Important limitation: the existing-record update path does not backfill `source_url`, which explains why a present-day provider artifact cannot be assumed for the ten historical empty rows. / 重要限制：现有记录的更新路径不会回填 `source_url`，因此不能假定十条历史空记录仍有可用的当前 provider 来源资产。

## C–D. Direct-detail measurement / 直达详情测量

- `DIRECT_DETAIL_ATTEMPTS = 0` for the three controls because none had an exact stored Place URL. `DIRECT_DETAIL_EXPECTED_DOMAIN_MATCH = 0`. / 三个控制项均没有精确的已存储 Place URL，因此 `DIRECT_DETAIL_ATTEMPTS = 0`，`DIRECT_DETAIL_EXPECTED_DOMAIN_MATCH = 0`。
- `DIRECT_COHORT_ATTEMPTS = 1`, for discovery `309`; Maps search was skipped. The page loaded in `9870 ms`. / `DIRECT_COHORT_ATTEMPTS = 1`，对应 discovery `309`；已跳过 Maps 搜索。页面在 `9870 ms` 内加载。
- That existing extractor returned a Google-owned `google.cn` domain. It is not a first-party merchant domain and is **not accepted** as an official website, regardless of the identity score. / 既有提取器返回了 Google 所有的 `google.cn` 域名。它不是商户第一方域名，**不得接受**为官网，无论身份评分为何。
- `DIRECT_COHORT_RESOLVED = 0`; `DIRECT_COHORT_NETWORK_RETRY = 0`; `DIRECT_COHORT_CONFIRMED_NO_WEBSITE = 0`; `DIRECT_COHORT_IDENTITY_REVIEW = 0`. The other ten rows had no exact URL and were not searched. / `DIRECT_COHORT_RESOLVED = 0`；`DIRECT_COHORT_NETWORK_RETRY = 0`；`DIRECT_COHORT_CONFIRMED_NO_WEBSITE = 0`；`DIRECT_COHORT_IDENTITY_REVIEW = 0`。其余十条没有精确 URL，未进行搜索。

## Decision / 决策

`ROOT_CAUSE_CONFIRMED = SOURCE_URL_COVERAGE_GAP (10/11 empty) plus unsafe Google-owned fallback on the only direct detail response; the direct-detail fast path is not proven.` / `ROOT_CAUSE_CONFIRMED = SOURCE_URL_COVERAGE_GAP（10/11为空）加上唯一直接详情响应中不安全的 Google 所有域名回退；直达详情快速路径尚未得到证明。`

The old search path had `OLD_RESOLVED = 0` and `OLD_NETWORK_RETRY = 11`. The direct experiment did not produce a legitimate resolved merchant website or a known-positive match, so it does not materially outperform the old path. No fast-path implementation is justified. / 旧搜索路径为 `OLD_RESOLVED = 0`、`OLD_NETWORK_RETRY = 11`。直达实验未产生合法的商户官网解析结果或正样本匹配，因此未实质优于旧路径；不具备实施快速路径的依据。

- `DIRECT_DETAIL_PATH_USED = true` for the one exact stored URL. / 对唯一精确已存储 URL，`DIRECT_DETAIL_PATH_USED = true`。
- `SEARCH_SKIPPED_WHEN_EXACT_SOURCE_URL_AVAILABLE = true` for that one URL; this cannot cover the ten empty records. / 对该唯一 URL，`SEARCH_SKIPPED_WHEN_EXACT_SOURCE_URL_AVAILABLE = true`；无法覆盖其余十条空记录。
- `NEXT_LEAD_AFTER_FAILURE_RUNS = NOT_EXERCISED` in the direct experiment because its only navigation loaded; existing lifecycle test remains green but no new fast path exists. / 直达实验唯一导航成功加载，因此 `NEXT_LEAD_AFTER_FAILURE_RUNS = NOT_EXERCISED`；既有生命周期测试仍通过，但不存在新的快速路径。
- `ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0`; `ORPHAN_CHROMIUM_PROCESS_COUNT = 0`. / `ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0`；`ORPHAN_CHROMIUM_PROCESS_COUNT = 0`。

## Regression / 回归

- Targeted lifecycle tests: `2 passed in 0.92s`. / 定向生命周期测试：`2 passed in 0.92s`。
- Full suite: `341 passed, 76 subtests passed in 64.16s`; `FAILED = 0`; `ERRORS = 0`. / 完整套件：`341 passed, 76 subtests passed in 64.16s`；`FAILED = 0`；`ERRORS = 0`。
- `FAST_PATH_IMPLEMENTED = false`; `V2_POLICY_CHANGED = false`; `MX_POLICY_CHANGED = false`; `PRODUCTION_FILES_IN_PATCH = none`. / `FAST_PATH_IMPLEMENTED = false`；`V2_POLICY_CHANGED = false`；`MX_POLICY_CHANGED = false`；`PRODUCTION_FILES_IN_PATCH = none`。

## Final state / 最终状态

`READY_FOR_FINAL_INVENTORY_REHEARSAL = false`. The concrete blocker is not V2/MX or the 45-second deadline: it is insufficient persisted Place-URL coverage and an unsafe Google-owned fallback result. Stop pending explicit authorization for a separate narrow remedy. / `READY_FOR_FINAL_INVENTORY_REHEARSAL = false`。具体阻塞不是 V2/MX 或 45 秒截止时间，而是已持久化 Place URL 覆盖不足及不安全的 Google 所有域名回退结果。等待针对独立窄修复的明确授权后再继续。
