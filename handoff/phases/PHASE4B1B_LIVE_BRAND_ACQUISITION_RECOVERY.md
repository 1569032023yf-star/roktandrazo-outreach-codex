# PHASE 4B.1B — 多平台品牌方获取恢复报告 / Live Brand Acquisition Recovery

## 结论 / Result

```makefile
PHASE = 4B.1B
RESULT = ENGINEERING_COMPLETE_LIVE_VALIDATION_BLOCKED
BASELINE_COMMIT = 470472401f64b68e536a4a2417df1cbf2ec47d20
BRANCH = codex/phase4b1b-live-brand-acquisition
NETWORK_EGRESS_AVAILABLE = false
DEVELOPMENT_ENV_NETWORK_BLOCKED = true
NETWORK_FAILURE_RETRY_FIXED = true
FAILED_URL_RETRIED_CORRECTLY = true
REAL_PROVIDER_DISCOVERY_CONNECTED = true
BRAND_OWNER_CHECK_CONNECTED = true
OFFICIAL_SITE_CHECK_CONNECTED = true
FIRST_PARTY_EXTRACT_CONNECTED = true
HISTORY_CHECK_CONNECTED = true (UNKNOWN fail-closed; no development history copy supplied)
MX_CHECK_CONNECTED = true (read-only DNS MX mechanism)
TIKTOK_PROVIDER_WORKING = false
AMAZON_PROVIDER_WORKING = false
WHOLESALE_PROVIDER_WORKING = false
PROVIDER_PAGES_ATTEMPTED = 0
PROVIDER_PAGES_FETCHED = 0
RAW_BRANDS_DISCOVERED = 0
DEDUPED_UNIQUE_BRANDS = 0
BRAND_OWNERS_CONFIRMED = 0
NEW_UNIQUE_BRAND_OWNERS = 0
OFFICIAL_SITES_VERIFIED = 0
FIRST_PARTY_EMAILS_FOUND = 0
B2B_EMAILS_FOUND = 0
HISTORY_CLEAN_BRANDS_WITH_EMAIL = 0
TIKTOK_NEW_BRANDS = 0
TIKTOK_B2B_EMAILS = 0
AMAZON_NEW_BRANDS = 0
AMAZON_B2B_EMAILS = 0
WHOLESALE_NEW_BRANDS = 0
WHOLESALE_B2B_EMAILS = 0
NETWORK_FAILURES = 0 (provider requests skipped by network preflight)
DIAGNOSTIC_DNS_FAILURES = 3
ACCESS_RESTRICTED = 0
HTTP_429 = 0
PARSE_EMPTY = 0
HISTORY_UNKNOWN = 0 (no candidates reached history check)
TOTAL_RUNTIME_SECONDS = 0.032 (network diagnostic)
BASELINE_TEST_FAILURES = 3
NEW_REGRESSION_FAILURES = 0
TARGETED_TESTS = 30 passed
FULL_SUITE = 519 passed; 135 subtests passed; 3 known baseline failures
FULL_UNITTEST = 519 passed; 135 subtests passed; 3 known baseline failures
COMPILEALL = PASS
GIT_DIFF_CHECK = PASS
ENGINEERING_READY = true
LIVE_END_TO_END_VALIDATED = false
READY_FOR_PRODUCTION_REVIEW = false
PRODUCTION_DB_WRITES = 0
PRODUCTION_DEPLOYMENT = false
WORKBUDDY_CHANGED = false
CANONICAL_INVENTORY_CHANGED = false
CITY_QUEUE_CHANGED = false
MAX_PAGES_CHANGED = false
V1_CHANGED = false
V2_CHANGED = false
MX_POLICY_CHANGED = false
HISTORY_RULES_RELAXED = false
SUPPRESSION_RULES_RELAXED = false
BOUNCE_RULES_RELAXED = false
SMTP_CONNECTIONS = 0
EMAILS_SENT = 0
FSP_CREATED = 0
SEND_AUTHORIZATION_CREATED = 0
COMMIT_SHA = pending
PUSH_SUCCESS = pending
```

本次达到工程修复级。实时公开网页验证未完成：诊断在请求来源页面之前发现系统 DNS 不可用，`HTTP_PROXY`/`HTTPS_PROXY` 配置的本机代理主机为 `127.0.0.1` 且 TCP 不可达。TikTok、Amazon、Faire 三个域名均得到 DNS 错误；没有继续请求来源页面。此结果说明当前开发环境出站路径受阻，不说明平台没有品牌，也不说明平台本身不可用。

Engineering fixes are complete. Live public-page validation remains blocked. Before requesting source pages, diagnostics found that system DNS was unavailable and the configured local proxy at `127.0.0.1` was unreachable over TCP. TikTok, Amazon, and Faire all failed at DNS resolution; provider-page requests were skipped. This establishes an egress problem in this development environment, not an absence of brands or a platform outage.

## 实施内容 / Changes

- `run_sources()` 现在只把成功解析、解析为空或明确永久无效的 URL 记入完成集；临时网络错误保留退避重试，429 暂停当前来源本轮，403/验证码记录为访问受限并停止自动访问。每来源原子写入状态、尝试历史、成功/失败 URL 和候选；损坏的 checkpoint 保留原文件并显式报错。
- 每 URL 最多 3 次尝试（含初次请求）；重试间隔按 60、120 秒指数退避，单次调用每 URL 最多请求一次。测试覆盖首次失败、等待退避后恢复成功、成功 URL 去重及来源间隔离。
- 品牌去重只在同一已验证官网域名下跨源合并；不再按名称别名合并。同名但不同已验证域名保留两条并标记 `identity_conflict`，冲突候选不进入后续增强。
- 官网状态与品牌身份状态分开保存。临时官网失败不抹除已确认的品牌身份。身份验证复用 `discovery` 现有第一方官网判定器，但必须先取到 HTTPS、TLS 成功、同主体的真实页面；Marketplace 域名、私有地址和跨主体/私有重定向不作为官网。
- 运行入口实际装配来源解析、品牌方确认、官网核验、现有第一方邮箱提取、只读历史检查和 MX 查询。品牌方确认要求市场/目录商品证据与已验证品牌官网同时成立。邮箱须有官网正文中的原文摘录、证据 URL、HTTP 状态、最终 URL 和官网身份核验；缺证据邮箱会被清空且不查询 MX。
- 候选、checkpoint、金丝雀报告、CSV 均只写开发 `output/brand_acquisition/phase4b1b/`。回放来源标为 `public_import`，夹具标为 `test_fixture/KNOWN_TEST_SEED`，均不会计入实时品牌数量。输出目录内 checkpoint 为独立目录。
- 历史库没有被假定存在。可显式配置 `BRAND_ACQUISITION_DEV_HISTORY_DB` 并设置 `BRAND_ACQUISITION_HISTORY_IS_DEVELOPMENT_COPY=true`，文件必须位于仓库 `output/brand_acquisition/dev_history/` 或 `data/development_history/`；未配置时状态保持 `UNKNOWN`。本次没有候选进入历史核查。
- 诊断仅报告代理变量是否存在、代理主机与 TCP 可达性，不输出凭据、路径或代理认证信息。没有代理轮换、身份轮换、验证码绕过或 SMTP 行为。

`REAL_PROVIDER_DISCOVERY_CONNECTED=true` 表示三个来源均有类目入口配置和真实页面解析器，且运行入口连接统一 fetcher；不代表本次抓取成功。指定类目 URL： [TikTok Shop 贺卡类目](https://shop.tiktok.com/us/k/greetings-cards)、[Amazon 贺卡搜索](https://www.amazon.com/s?k=greeting+cards)、[Faire Holiday Cards 目录](https://www.faire.com/category/Holiday%20Cards)。这些页面本次均未请求。

## 验证 / Verification

- `TARGETED_TESTS=31 passed`，覆盖三来源解析、Amazon 品牌与卖家区分、跨源安全去重、同名冲突、品牌方证据门槛、官网与邮箱证据、猜测/目录邮箱拒绝、历史与 MX 失败关闭、超时/429/403/验证码状态、重试恢复、成功去重、损坏 checkpoint、私有地址和危险跳转拒绝、夹具实时计数隔离、导入页来源与时区校验及运行回调接线。
- `FULL_UNITTEST=519 passed; 135 subtests passed; 3 failed`。失败为 `TestSourceAudit.test_archived_dashboards_have_disable_marker`、`TestInventoryArchival.test_archived_scripts_have_disable_marker`、`TestSingleSmtpAuthority.test_archived_scripts_fail_closed`，三者均要求仓库缺失的 `_archived_scripts/2026-08-07` 目录。相同三项已在 4B.1A/本阶段基线出现，故 `BASELINE_TEST_FAILURES=3`、`NEW_REGRESSION_FAILURES=0`；未添加假归档、删除或跳过测试。
- `COMPILEALL=PASS`（全仓库；存在既有 `facebook_enrichment/fb_batch_runner.py` 非法转义 `SyntaxWarning`）。`GIT_DIFF_CHECK=PASS`。
- 运行时诊断：DNS=false；HTTPS 公网响应=false；本机代理配置=true、代理主机=`127.0.0.1`、可达=false；三个来源状态=`DNS_ERROR`；provider pages attempted/fetched=`0/0`；实时候选/已验证官网/官网商务邮箱=`0/0/0`。
- 另有独立搜索工具能够返回缓存索引快照，但不是本次 Python fetcher 的实时来源响应，未作为发现候选、官网或邮箱证据，也不计入任何产出。

## 安全与生产隔离 / Safety and production boundary

本次未访问或写入生产数据库，未改动生产文件、WorkBuddy、Inventory、SAFE40、城市队列、`max_pages`、V1/V2、MX 策略、抑制或退信规则；未部署；未创建 FSP 或发送授权；SMTP 连接和邮件发送均为零。开发品牌候选没有自动加入 lead、SAFE、邮箱数据库或发送计划。

No production database or production file was accessed or changed. WorkBuddy, Inventory, SAFE40, city queues, `max_pages`, V1/V2, MX policy, suppression rules, and bounce rules were unchanged. There was no deployment, FSP, send authorization, SMTP connection, email send, lead creation, or SAFE addition.

## 交接判断 / Handoff

`ENGINEERING_READY=true` 仅表示工程修复、定向测试、编译与差异检查达到开发评审级。因为实时网页、第一方邮箱和历史副本均未验证，`LIVE_END_TO_END_VALIDATED=false`、`READY_FOR_PRODUCTION_REVIEW=false`。要完成用户所需的真实数量验证，需在 DNS/代理正常且获准联网的开发环境中重新运行 `--mode live-public`；随后仍须提供经批准的开发历史副本才能评估历史干净数量。

`ENGINEERING_READY=true` indicates development-level engineering and test readiness only. Since live pages, first-party email, and a history copy were not validated, `LIVE_END_TO_END_VALIDATED=false` and `READY_FOR_PRODUCTION_REVIEW=false`. To measure real yield, rerun `--mode live-public` in an authorized development environment with working DNS/egress, then provide an approved development history copy for history-clean evaluation.
