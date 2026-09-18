# Phase 4A.3K — Duplicate Discovery Website/Provenance Backfill / 重复发现官网与来源回填

## Scope and safety / 范围与安全

- Started from `0e00bf188a889c164d53790979fab61fe21da704`. The only production-source changes are `discovery/discovery_service.py` and `discovery/providers/browser_maps_scraper.py`. / 基于 `0e00bf188a889c164d53790979fab61fe21da704` 开始。唯一的生产源代码修改为 `discovery/discovery_service.py` 和 `discovery/providers/browser_maps_scraper.py`。
- A fresh SQLite online-backup production database copy passed `PRAGMA integrity_check = ok`. Production database writes, production file changes, SMTP, IMAP, deployment, scheduler changes, full Inventory, and Maps search were all `0`. / 新鲜 SQLite 在线备份的生产数据库副本通过 `PRAGMA integrity_check = ok`。生产数据库写入、生产文件变更、SMTP、IMAP、部署、调度变更、完整 Inventory 与 Maps 搜索均为 `0`。

## A. Update-path gap / 更新路径缺口

| Path / 路径 | Website / 官网 | Source URL / 来源 URL |
|---|---|---|
| New insert / 新插入 | persists / 持久化 | persists / 持久化 |
| Existing duplicate update before fix / 修复前的重复更新 | discarded / 丢弃 | discarded / 丢弃 |
| Existing duplicate update after fix / 修复后的重复更新 | backfills only an empty field from a valid BrowserMaps website / 仅从合法 BrowserMaps 官网回填空字段 | backfills only an empty field from an exact Google Maps Place URL / 仅从精确 Google Maps Place URL 回填空字段 |

`DUPLICATE_ENRICHMENT_GAP_CONFIRMED = true`. `_upsert_result()` inserted both fields on new rows but its prior duplicate update omitted both fields. / `DUPLICATE_ENRICHMENT_GAP_CONFIRMED = true`。`_upsert_result()` 会在新记录插入两个字段，但此前的重复更新遗漏两者。

## C–D. Narrow repair / 窄修复

- The duplicate path now backfills `source_url` only when the stored value is empty, `provider == browser_maps`, and the incoming URL is an exact Google Maps `/maps/place/` URL. It never overwrites a non-empty value or synthesizes a URL. / 重复路径现在仅在已存值为空、`provider == browser_maps`、且传入 URL 为精确 Google Maps `/maps/place/` URL 时回填 `source_url`。绝不覆盖非空值，也绝不合成 URL。
- It backfills `website` only when the stored value is empty and the incoming website is valid and non-Google-owned; `normalized_domain` is filled only with that accepted website. Existing websites, source URLs, validation states, identity matching, evidence, history, V2, and MX rules remain unchanged. / 仅当已存官网为空且传入官网合法、非 Google 自有域名时才回填 `website`；`normalized_domain` 仅据此被接受官网回填。已有官网、来源 URL、验证状态、身份匹配、证据、历史、V2 与 MX 规则均未改变。
- Google-owned and redirect/internal host families—including `google.com`, `google.cn`, regional `google.*`, `goo.gl`, `g.page`, `googleusercontent.com`, `googleapis.com`, `gstatic.com`, and `googleadservices.com`—are rejected by BrowserMaps external-link filtering. The existing explicitly permitted `sites.google.com` and `*.business.site` handling remains. / BrowserMaps 外链过滤现在拒绝 Google 自有和重定向/内部主机族，包括 `google.com`、`google.cn`、区域性 `google.*`、`goo.gl`、`g.page`、`googleusercontent.com`、`googleapis.com`、`gstatic.com`、`googleadservices.com`。既有明确允许的 `sites.google.com` 与 `*.business.site` 处理保持不变。

## B, F–H. Production-cache replay on copy / 生产缓存副本重放

- Only one cache JSON matched the exact eleven-row cohort and was copied into development quarantine; it produced one duplicate replay for discovery `309`. The eight previously observed duplicate Maps results were not identifiable as matching production cache assets in this replay. / 只有一个缓存 JSON 匹配固定十一条 cohort，并被复制到开发隔离区；它仅产生 discovery `309` 的一次重复重放。此前观察到的八条重复 Maps 结果在本次重放中无法识别为匹配的生产缓存资产。
- `CACHE_MATCH_COUNT = 1`; `CACHE_MATCH_WITH_WEBSITE = 0`; `CACHE_MATCH_WITH_MAPS_SOURCE_URL = 1`. / `CACHE_MATCH_COUNT = 1`；`CACHE_MATCH_WITH_WEBSITE = 0`；`CACHE_MATCH_WITH_MAPS_SOURCE_URL = 1`。
- `COHORT_SOURCE_URL_BEFORE = 1`; `COHORT_SOURCE_URL_AFTER = 1`; `SOURCE_URL_BACKFILLED = 0`. `COHORT_WEBSITE_BEFORE = 0`; `COHORT_WEBSITE_AFTER = 0`; `WEBSITE_BACKFILLED = 0`. / `COHORT_SOURCE_URL_BEFORE = 1`；`COHORT_SOURCE_URL_AFTER = 1`；`SOURCE_URL_BACKFILLED = 0`。`COHORT_WEBSITE_BEFORE = 0`；`COHORT_WEBSITE_AFTER = 0`；`WEBSITE_BACKFILLED = 0`。
- The one replay carried no incoming website and an already-present exact Maps source URL, so the real upsert path had nothing safe to backfill. No manual field update was used. / 唯一的重放记录没有传入官网，且其精确 Maps 来源 URL 已存在，因此真实 upsert 路径没有可安全回填的数据。未使用任何手动字段更新。
- `GOOGLE_OWNED_WEBSITE_REJECTED = 0` in real cache replay because no incoming Google-owned website existed; targeted tests prove rejection of `google.com`, `google.cn`, and internal redirects. / 真实缓存重放中没有传入 Google 自有官网，因此 `GOOGLE_OWNED_WEBSITE_REJECTED = 0`；定向测试已证明会拒绝 `google.com`、`google.cn` 和内部重定向。
- `BACKFILLED_WEBSITE_ROWS = 0`; consequently postprocess, direct-detail measurement, and V2/MX recomputation were not run. This preserves the authorization boundary and avoids manufacturing output from non-backfilled rows. / `BACKFILLED_WEBSITE_ROWS = 0`；因此未运行后处理、直达详情测量或 V2/MX 重算。这保持了授权边界，并避免从未回填记录制造结果。

## Regression / 回归

- Targeted tests: `27 passed, 9 subtests passed in 15.33s`, covering empty-field backfill, non-overwrite, invalid/non-Place source rejection, Google domains, legitimate merchant/hosted-site links, no guessed URL, existing official evidence preservation, discovery service, and lifecycle cleanup. / 定向测试：`27 passed, 9 subtests passed in 15.33s`，覆盖空字段回填、禁止覆盖、无效/非 Place 来源拒绝、Google 域名、合法商户/托管站点链接、不猜测 URL、保留既有官方证据、发现服务与生命周期清理。
- Full suite: `346 passed, 76 subtests passed in 69.43s`; `FAILED = 0`; `ERRORS = 0`. / 完整套件：`346 passed, 76 subtests passed in 69.43s`；`FAILED = 0`；`ERRORS = 0`。

## Decision / 决策

- `DUPLICATE_ENRICHMENT_PATH_FIXED = true` at code and test level. / `DUPLICATE_ENRICHMENT_PATH_FIXED = true`，代码与测试层面均已修复。
- `SOURCE_URL_FAST_PATH_EVIDENCE_SUPPORTED = false`: the real matching cache did not backfill any new source URL, so no new direct-detail evidence exists. / `SOURCE_URL_FAST_PATH_EVIDENCE_SUPPORTED = false`：真实匹配缓存没有回填新的来源 URL，因此不存在新的直达详情证据。
- `READY_FOR_FINAL_INVENTORY_REHEARSAL = false`: real replay demonstrated no useful upstream asset recovery or downstream progress, although the narrow duplicate-data-loss defect is fixed. / `READY_FOR_FINAL_INVENTORY_REHEARSAL = false`：真实重放未证明有用的上游资产恢复或下游进展，尽管窄范围的重复数据丢失缺陷已修复。

All copied cache, production-derived database copies, browser cache, and temporary test artifacts were removed from development quarantine after measurement and are not committed. / 所有复制缓存、生产派生数据库副本、浏览器缓存和临时测试产物均在测量后从开发隔离区删除，且不会提交。
