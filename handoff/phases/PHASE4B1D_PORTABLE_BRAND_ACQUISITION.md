# PHASE 4B.1D — 离线优先的可移植品牌获取引擎
# PHASE 4B.1D — Offline-First Portable Brand Acquisition Engine

## 交付结论 / Delivery summary

本阶段基于 `59daacc37b1a082e3e631650e805317b6f1639d4`，在 `codex/phase4b1d-portable-brand-acquisition` 完成离线优先工程实现。未发起外网请求；没有把合成夹具或导入快照计作实时品牌或邮箱。

This phase is based on `59daacc37b1a082e3e631650e805317b6f1639d4` and implements the offline-first engine on `codex/phase4b1d-portable-brand-acquisition`. No public-network requests were made. Synthetic fixtures and imported snapshots are not counted as live brands or emails.

| 项目 / Item | 结果 / Result |
|---|---|
| 离线优先引擎 / Offline-first engine | 已实现；导入与重放不联网 / Implemented; import and replay are offline |
| 官网候选解析 / Official-site candidate resolver | 已实现；只采集显式 URL，不猜域名 / Implemented; explicit URLs only, no domain guessing |
| 采集清单 / Capture manifest | 已实现 SHA-256、路径边界、大小、时间和来源字段检查 / Implemented with SHA-256, path, size, time, and provenance checks |
| 公开页面导入 / Public-page import | 已实现；导入内容一律只是 discovery evidence，未认证的实时声明会降级 / Implemented; imports remain discovery evidence and unauthenticated live claims are downgraded |
| 可移植执行器 / Portable runner | 已实现四种模式；禁网时 `capture-public` 在请求前失败关闭 / Four modes implemented; `capture-public` fails closed before requests when network is disabled |
| 品牌所有者核验 / Brand-owner verification | 已接入既有正式站点验证回调；未经确认的商家保持 `IDENTITY_UNVERIFIED` / Integrated with existing site verification; unconfirmed merchants remain unverified |
| 官网第一方邮箱 / First-party email | 复用现有提取逻辑，并增加占位邮箱和跨域归属检查 / Existing extractor reused with placeholder and cross-domain affiliation gates |
| 历史接口 / History adapter | 复用只读 opt-in adapter；无开发副本时状态为 `UNKNOWN` / Existing read-only opt-in adapter; `UNKNOWN` without an approved development copy |
| SAFE40、生产和发送 / SAFE40, production, and sending | 未触及 / Untouched |

## 产量与证据边界 / Counts and evidence boundary

本次没有执行实时采集或导入客户页面：离线业务产物中的候选数、导入候选数、实时品牌数、实时验证邮箱数均为 0。合成 parser fixtures 只在测试中使用，不能视作客户。

No live capture or customer-page import was run. Candidate, imported-candidate, live-brand, and live-verified-email counts in the offline business output are all zero. Synthetic parser fixtures were used only in tests and are not customers.

| 指标 / Metric | 数值 / Value |
|---|---:|
| RAW_BRANDS_DISCOVERED | 0 |
| DEDUPED_UNIQUE_BRAND_CANDIDATES | 0 |
| BRAND_OWNER_CONFIRMED | 0 |
| OFFICIAL_SITE_CANDIDATES_FOUND | 0 |
| OFFICIAL_SITES_VERIFIED | 0 |
| FIRST_PARTY_EMAILS_FOUND / B2B_EMAILS_FOUND | 0 / 0 |
| HISTORY_CLEAN_BRANDS_WITH_EMAIL | 0 |
| OFFLINE_FIXTURE_BRANDS / IMPORTED_PUBLIC_BRAND_CANDIDATES | 0 / 0 |
| LIVE_DISCOVERED_BRANDS / LIVE_VERIFIED_OFFICIAL_EMAILS | 0 / 0 |
| PLACEHOLDER_EMAIL_CASES_REJECTED | 1 deterministic pipeline test case |

## 验证 / Validation

- 定向测试：`tests.test_brand_acquisition` 与 `tests.test_brand_acquisition_offline`，43 项通过。
- 全套：419 项，405 项通过、2 项失败、12 项错误。失败为两项历史归档文件审计（本检出缺少 `_archived_scripts/2026-08-07/` 文件）；错误包括 `.env` 未配置、归档目录缺失、Python launcher/DB routing 子进程前置条件。完整日志保存在本地忽略输出 `output/brand_acquisition_test_tmp/full_suite.log`，不作为业务数据提交。
- 新代码回归：定向品牌获取测试中 0 失败；全套的 2 failures/12 errors 并未定位到本次新增代码。
- `compileall`：通过。
- `git diff --check`：通过。
- 禁网检查：`CODEX_SANDBOX_NETWORK_DISABLED=1` 时 runner 返回 `NETWORK_POLICY_BLOCKED` 且 `requests_made=0`。没有尝试规避。

- Targeted tests: `tests.test_brand_acquisition` and `tests.test_brand_acquisition_offline`; 43 passed.
- Full suite: 419 tests; 405 passed, 2 failed, and 12 errored. The failures are archived-file audits because this checkout lacks files under `_archived_scripts/2026-08-07/`; errors include missing `.env`, missing archive directory, and Python launcher/DB-routing subprocess prerequisites. Full detail is in the ignored local output `output/brand_acquisition_test_tmp/full_suite.log`; it is not committed as business data.
- New-code regression: 0 failures in targeted brand-acquisition tests. The 2 failures/12 errors in the full suite were not traced to this change.
- `compileall`: passed.
- `git diff --check`: passed.
- Network gate: with `CODEX_SANDBOX_NETWORK_DISABLED=1`, the runner returns `NETWORK_POLICY_BLOCKED` with `requests_made=0`. No bypass was attempted.

## 后续 4B.1E / Next phase 4B.1E

1. 在获准且明确可联网的**开发**环境，将来源目录替换/确认成实际可访问的公开类目 URL，先按每来源最多 2 页执行 live canary；验证 live page、品牌归属、官网身份和第一方邮箱四项端到端条件。
2. 复核来源网站条款、真实页面结构、页面限速与允许的访问配额；遇到登录、验证码、访问限制或 429，停止该来源，不绕过。
3. 若需要历史去重，先由负责人提供明确标记为开发只读副本的历史快照及 schema 映射；不得读取生产库。未知历史继续 fail closed。
4. 用获准的实时证据校验导入清单与页面来源；SHA-256 只校验字节完整性，不是来源认证。
5. 在人工审核独立完成前不将候选提升到任何 SAFE 池；发送保持冻结。本交付不是生产审查或部署授权。

1. In an authorized development environment with confirmed network access, verify/replace catalog URLs with genuinely reachable public category pages and run a live canary capped at two pages per source. Validate the live-page, owner, official-site, and first-party-email conditions end to end.
2. Review site terms, actual page structures, rate limits, and permitted quotas. Stop a source on login, CAPTCHA, access restriction, or 429; do not bypass.
3. If history matching is needed, obtain an explicitly designated read-only development snapshot and schema mapping. Never read production DB. Unknown history remains fail-closed.
4. Authenticate imported page provenance through authorized live evidence; SHA-256 checks byte integrity only.
5. Do not promote candidates into any SAFE pool before separate human review; sending remains frozen. This delivery is not production-review or deployment authorization.

## 固定安全声明 / Safety declarations

```text
PHASE = 4B.1D
BASELINE_COMMIT = 59daacc37b1a082e3e631650e805317b6f1639d4
NEW_BRANCH = codex/phase4b1d-portable-brand-acquisition
NETWORK_POLICY_BYPASS_ATTEMPTED = false
PRODUCTION_DB_WRITES = 0
PRODUCTION_DEPLOYMENT = false
WORKBUDDY_CHANGED = false
SMTP_CONNECTIONS = 0
EMAILS_SENT = 0
LIVE_VALIDATION_PENDING_AUTHORIZED_ENVIRONMENT = true
```
