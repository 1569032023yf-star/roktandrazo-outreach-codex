# PHASE 4B.1A — 多平台卡牌与纸制品品牌方批量获取引擎 / Multichannel Cards and Paper Goods Brand Acquisition

## 范围与安全边界 / Scope and safety

本阶段新增隔离的 `brand_acquisition/` 引擎，仅从公开 TikTok Shop、Amazon 与批发目录页面读取候选线索；先跨来源去重，再查历史、确认品牌方、核验官网并调用现有 discovery 第一方邮箱提取器。候选、来源进度和计量仅写开发侧 JSON。品牌发现与现有零售门店 SAFE40 严格分离；没有将候选写入 lead、邮箱、SAFE 或发送计划。/ This phase adds an isolated `brand_acquisition/` engine. It reads public TikTok Shop, Amazon, and wholesale-directory signals; deduplicates across sources before history, owner, official-site, and first-party email checks; and writes only development JSON. The brand pool is separate from retail SAFE40. No leads, SAFE entries, send plans, or email records were created.

- `DEV_BASELINE_COMMIT=0cb41c23c146a7c149d7cce8f2c4ded89d191e3c`
- `BRAND_ENGINE_IMPLEMENTED=true`（独立引擎、公开源适配器、持久化断点、历史只读接口、失败关闭过滤、漏斗与 canary 命令）。/ Independent engine, public-source parsers, resumable checkpoints, explicit read-only history adapter, fail-closed gates, funnel metrics, and canary command are implemented.
- `TIKTOK_PROVIDER_WORKING=false`; `AMAZON_PROVIDER_WORKING=false`; `WHOLESALE_PROVIDER_WORKING=false`：canary 对应 1、1、2 个页面均未抓取成功，错误为网络层 `URLError`。这是当前运行环境出网失败，不等同于平台拒绝或解析器失效。各解析器以归约的代表性结构 fixture 测试。/ None of the four canary pages fetched successfully; each source failed with a network-layer `URLError`. This establishes runtime egress failure only, not platform denial or parser failure. Parsers were exercised against reduced representative fixtures.
- 原始发现、去重候选、确认所有者、真实官网邮箱均为 0；历史开发只读副本不可用，因此历史状态若出现候选也必须是 `UNKNOWN`，不会计入历史干净池。/ Zero real candidates were fetched or confirmed. No development history copy was supplied; any candidates would remain `UNKNOWN` and excluded from the history-clean pool.
- `NEW_UNIQUE_BRAND_OWNERS=0`; `HISTORY_CLEAN_BRANDS_WITH_EMAIL=0`; `BEST_PERFORMING_SOURCE=undetermined`; `TOTAL_RUNTIME=0.8 seconds`（总管线约值；来源运行时间为 Amazon 0.062s、TikTok 0.065s、Wholesale 0.078s）。无可比较的成功源。/ No new owners or history-clean emails were obtained. No source can be ranked; total pipeline runtime was approximately 0.8 seconds, with per-source runtimes recorded in the JSON result.
- 可以从未跟踪的 `output/brand_acquisition/phase4b1a/brand_candidates.json` 及 source checkpoint 查看逐候选/来源记录；本次候选文件为空，不含客户个人数据。/ Per-candidate and per-source records reside under ignored, untracked `output/brand_acquisition/phase4b1a/`; this run's candidate file is empty.

## 身份与证据约束 / Identity and evidence controls

平台店铺、经销商、商品品牌声明和批发目录条目都先标记为未确认；不会自动等同品牌所有者。只有通过显式 owner callback 才可进入品牌方路径；只有官方站身份回调成功后才提取官网邮箱。邮箱必须来自第一方页面证据并通过基本 hygiene；MX 和历史检查可注入，缺省失败关闭。未核实商家不会被自动提升到 SAFE。/ Storefronts, resellers, product brand claims, and directory listings remain unconfirmed. Explicit owner confirmation is required before the owner path, and official-site identity verification is required before mailbox extraction. Emails require first-party page evidence and basic hygiene. MX/history callbacks fail closed by default. No unverified merchant enters SAFE.

独立网页研究中观察到 TikTok Shop 的公开商店快照（抓取时间陈旧）、Faire 公开目录摘要；Amazon 页面返回 503。它们仅作为接口规划背景，`counts_in_pipeline=false`，不是引擎的实时发现候选。Amazon 自动 canary 实际遇到的是网络 `URLError`。/ Separate web research saw a stale indexed TikTok shop snapshot and public Faire directory summaries; Amazon returned HTTP 503 in browser research. These are contextual observations only (`counts_in_pipeline=false`), not pipeline discoveries. The automated Amazon canary itself reported a network `URLError`.

## 吞吐与恢复 / Throughput and resume

默认上限：HTTP workers 4、浏览器 workers 1、每批候选 90、每来源页面 3、每来源候选 30。源并行且各自 checkpoint；访问失败记录后独立跳过，限流/访问挑战停止该源；不使用代理、验证码绕过或账号轮换。/ Defaults: at most four HTTP workers, one browser worker, 90 candidates total, three pages and 30 candidates per source. Sources run independently with separate checkpoints; failures are recorded and skipped, while rate limits/access challenges stop that source. No proxies, challenge bypass, or account rotation.

## 验证 / Verification

- `TARGETED_TESTS=13 passed`（公开结构 fixture、所有者与转售商区分、跨来源去重、官网与第一方证据、历史排除、MX 失败关闭、受限访问降级、断点恢复、来源隔离、漏斗与配额）。/ 13 targeted tests passed.
- `FULL_SUITE=501 passed; 135 subtests passed; 3 failed`。三项失败分别为 `test_dashboard_consolidated`、`test_inventory_followup`、`test_single_smtp_authority` 对 `_archived_scripts/2026-08-07` 归档文件的存在性断言；该目录在此新鲜 main 基线中不存在。/ The three failures require absent `_archived_scripts/2026-08-07` files in this fresh main baseline; no other full-suite test failed.
- `COMPILEALL=PASS`（全仓库；存在仓库既有 `facebook_enrichment/fb_batch_runner.py` 非法转义 SyntaxWarning）。/ Repository-wide compileall passed with a pre-existing invalid-escape SyntaxWarning.
- `GIT_DIFF_CHECK=PASS`；提交前缓存差异检查也通过。4A.8Q 的发现服务、城市队列、SAFE40、V1/V2、WorkBuddy 和发送代码无本次修改。/ Git diff checks passed. Discovery service, city queue, SAFE40, V1/V2, WorkBuddy, and sending code were not changed.

## 决策 / Decision

- `READY_FOR_PRODUCTION_REVIEW=false`：自动公共源在此环境没有成功抓取；无生产历史只读副本；全套测试有三项基线归档缺失失败；身份政策与真实候选数据仍需人工评审。代码可供开发审查，不能作为生产准入或调度授权。/ Not ready for production review: no source fetch succeeded in this environment, no read-only production-history copy was available, three baseline archive-dependent tests failed, and identity policy/real candidates still need human review. The code is ready for development review only, not production activation.

## 最终字段 / Required fields

```makefile
BRAND_ENGINE_IMPLEMENTED = true
TIKTOK_PROVIDER_WORKING = false (network URLError; 0/1 pages fetched)
AMAZON_PROVIDER_WORKING = false (network URLError; 0/1 pages fetched)
WHOLESALE_PROVIDER_WORKING = false (network URLError; 0/2 pages fetched)
NEW_UNIQUE_BRAND_OWNERS = 0
HISTORY_CLEAN_BRANDS_WITH_EMAIL = 0
TOTAL_RUNTIME = approximately 0.8 seconds
BEST_PERFORMING_SOURCE = undetermined
PRODUCTION_DB_WRITES = 0
PRODUCTION_DEPLOYMENT = false
WORKBUDDY_CHANGED = false
SMTP_CONNECTIONS = 0
EMAILS_SENT = 0
TARGETED_TESTS = 13 passed
FULL_SUITE = 501 passed; 135 subtests passed; 3 baseline archive-dependent failures
COMPILEALL = PASS (pre-existing SyntaxWarning)
GIT_DIFF_CHECK = PASS
READY_FOR_PRODUCTION_REVIEW = false
BRANCH = codex/phase4b1a-brand-acquisition
COMMIT_SHA = a36dd1742cb644e04c1235e7120c9f17d285c495
PUSH_SUCCESS = pending
```

代码提交：`a36dd1742cb644e04c1235e7120c9f17d285c495`。/ Feature commit: `a36dd1742cb644e04c1235e7120c9f17d285c495`.
