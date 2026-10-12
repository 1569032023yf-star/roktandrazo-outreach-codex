# PHASE 4B.1E — 获准开发验收手册 / Authorized Development Canary Runbook

## 适用范围 / Scope

仅用于明确获准、正常可联网的隔离开发环境。当前 Codex 环境禁网，未执行以下 live 命令。不得修改或绕过 `CODEX_SANDBOX_NETWORK_DISABLED`。这不是生产部署、生产数据库访问、发信或调度器变更授权。

Use only in an explicitly authorized isolated development environment with normal network access. Current Codex networking is disabled; live commands below were not executed. Never alter or bypass `CODEX_SANDBOX_NETWORK_DISABLED`. This is not authorization to deploy, access production DB, send email or change schedulers.

## 1. 核对版本 / Verify revision

```powershell
git remote -v
git branch --show-current
git status -sb
git log -5 --oneline --decorate
git merge-base --is-ancestor 99350124604a54b3457e34e2285bf4fb7ccdfe5d HEAD
git ls-remote --heads origin codex/phase4b1e-industry-directory-acquisition
```

远端应为 `1569032023yf-star/roktandrazo-outreach-codex`，分支为 `codex/phase4b1e-industry-directory-acquisition`，基线为上述 SHA。核对最终交付的提交 SHA，保全已有输出。不要 force push、重置或合并 main。

Remote must be `1569032023yf-star/roktandrazo-outreach-codex`, branch `codex/phase4b1e-industry-directory-acquisition`, with the stated ancestor. Compare the final delivery SHA and preserve existing output. Do not force-push, reset or merge main.

## 2. 离线导入 / Offline import

复用 4B.1D capture schema；source_platform 增加 `toyfair`、`gca`、`nynow`、`astra`。每页需 URL、final_url、带时区 captured_at、capture_id、来源、SHA-256、相对 content_file、HTTP 状态、方法、类别及 data_origin。`page_category=official_site` 不重新当目录发现页解析。

Reuses the 4B.1D capture schema, adding the four directory source identifiers. Each page requires requested/final URLs, timezone timestamp, capture ID/source, SHA-256, relative content path, HTTP status, method/category and origin. Official-site captures are not reparsed as directory discovery pages.

```powershell
python scripts/run_industry_directory_canary.py --mode validate-manifest --manifest output/brand_acquisition/phase4b1e/synthetic_captures/capture_manifest.json
python scripts/run_industry_directory_canary.py --mode import-pages --manifest output/brand_acquisition/phase4b1e/synthetic_captures/capture_manifest.json --output-dir output/brand_acquisition/phase4b1e/offline_fixture_replay
python scripts/run_industry_directory_canary.py --mode replay --manifest output/brand_acquisition/phase4b1e/synthetic_captures/capture_manifest.json --output-dir output/brand_acquisition/phase4b1e/offline_fixture_replay
```

示例合成 manifest 仅在当前本地忽略目录，未提交。其他开发环境可通过测试模块中的确定性 fixture 生成示例，或提供获准公开页面快照。导入不联网、不确认官网/邮箱；即使 manifest 声称 LIVE_PUBLIC_CAPTURE，也降级到 OFFLINE_IMPORT 指标（内部标签 AUTHORIZED_PUBLIC_IMPORT）。完整哈希只证明字节未变，不认证网页来源、TLS 或身份。

The synthetic manifest exists only in the current local ignored directory and is not committed. Another development host may generate examples from deterministic test fixtures or supply authorized public snapshots. Import does not network or qualify sites/emails; claimed LIVE_PUBLIC_CAPTURE is downgraded to OFFLINE_IMPORT metrics (internal AUTHORIZED_PUBLIC_IMPORT). Hashes authenticate unchanged bytes, not source, TLS or identity.

## 3. 小规模公开页面 canary / Small public-page canary

先在实际网站核对条款、访问权限、真实目录入口和 DOM。默认来源来自用户指定入口，工程未证明这些入口当前可访问。ASTRA 如需要会员登录、挑战或权限，不继续；不能为四来源指标绕过限制。可用 schema_version 1.0 的 catalog 只选择已获准公开来源，每来源最多两项 URL。

First review actual terms, permissions, directory entrances and DOM. Defaults are the user-provided entrances, whose current accessibility is not certified. Stop ASTRA if login, challenge or permission is required; never bypass restrictions to satisfy source counts. A schema_version 1.0 catalog can select only approved public sources, with at most two URLs per source.

```powershell
python scripts/run_industry_directory_canary.py --mode capture-public --output-dir output/brand_acquisition/phase4b1e/authorized_live
# 可选已核对目录配置 / Optional reviewed directory catalog
python scripts/run_industry_directory_canary.py --mode capture-public --catalog output/brand_acquisition/phase4b1e/approved_directory_catalog.json --output-dir output/brand_acquisition/phase4b1e/authorized_live
```

固定上限：目录页 2/来源、HTTP worker ≤4、browser lane=1、原始候选 ≤90；四来源时每来源22，总88。官网抓取复用现有 HTTPS、安全重定向和每站页面预算，不提供自动登录或浏览器绕过。浏览器专用页面未被正常 HTTP 解析时按 PARSE_EMPTY/限制/网络状态记录，不声称没有企业。

Limits: two directory pages per source, HTTP workers ≤4, one browser lane and ≤90 raw candidates; four sources retain 22 each, total 88. Official-site fetching reuses existing HTTPS, safe redirects and per-site budgets. No login or browser bypass is provided. Browser-only pages that HTTP cannot parse remain PARSE_EMPTY/restricted/network outcomes, never proof of no organizations.

## 4. 开发历史只读副本 / Read-only development history copy

默认不打开任何数据库，history=UNKNOWN。需要历史验收时由负责人提供明确批准的开发只读快照及 schema，校验路径确为开发副本，不能指向生产库。副本不要提交 Git。不提供副本或 schema 失配时保持 UNKNOWN。

No database is opened by default; history stays UNKNOWN. History acceptance requires an explicitly approved read-only development snapshot and schema from its owner, with its path verified as a development copy. Never point to production or commit the copy. Missing or incompatible copies remain UNKNOWN.

```powershell
python scripts/run_industry_directory_canary.py --mode capture-public --output-dir output/brand_acquisition/phase4b1e/authorized_live --development-history-copy output/brand_acquisition/phase4b1e/history/approved_development_copy.sqlite --confirm-development-history-copy
```

此显式选项复用 `HistoryChecker` 的 SQLite mode=ro 与 PRAGMA query_only。没有提供副本的本次交付未执行此命令，不能声称历史已清洁。

The explicit option reuses `HistoryChecker` with SQLite mode=ro and PRAGMA query_only. No approved copy was supplied for this delivery, so the command was not executed and clean history is not claimed.

## 5. 输出与验收 / Output and acceptance

查看 `live_directory_result.json`、`brand_candidates.json`、`source_checkpoints/source_<source>.json`、`captures/capture_manifest.json`。每次成功采集立即保存 manifest；失败来源复用原有退避与最多3次尝试。已有成功目录页不重复抓取，未完成站点可重试，损坏证据/断点保留并失败关闭。需要重新核验 PARSE_EMPTY 或权限改变的页面时使用新的独立输出目录并保留旧审计，不修改旧断点伪造成功。

Review the result, candidate, source-checkpoint and capture-manifest files. Successful captures immediately update the manifest. Failed sources use existing backoff and at most three attempts; successful directory pages are skipped, unfinished sites can retry, and corrupt evidence/checkpoints are preserved fail-closed. For a changed layout or permissions after PARSE_EMPTY, use a new isolated output directory and preserve prior audit records.

核对目录组织名称、地区、年份及品类；只处理记录内显式 URL。逐条核对第一方官网匹配、邮箱原文、evidence URL/excerpt、checked_at、HTTP/final_url、history 和 MX。目录登记不证明品牌所有权或真实采购意向。名称-only 项目只能算发现。供应商、错误品类、冲突、占位或跨域归属失败不得计作合格客户。

Check names, geography, year and categories; use only record-scoped explicit URLs. Review site matching, verbatim email, evidence URL/excerpt, timestamp, HTTP/final URL, history and MX per record. Directory registration proves neither ownership nor buying intent. Name-only entries count only as discovery. Suppliers, irrelevant categories, identity conflicts, placeholders and failed cross-domain affiliation are not qualified customers.

指标按 TEST_FIXTURE、OFFLINE_IMPORT、LIVE_PUBLIC_CAPTURE 分开；主指标只取真实 LIVE_PUBLIC_CAPTURE。模拟传输测试的临时 LIVE 标签不可汇入业务报告。原始组织计数为上限内保留的发现记录；超限页面的解析总数在 source checkpoint 的 candidate_count，不能把截断后数量声称为整个目录总量。官网/邮箱不得缺证据；历史 UNKNOWN 或 MX 非 ok 的 HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL 必须为0。

Metrics separate fixtures, imports and live captures; headlines are live-only. Temporary mocked-transport LIVE labels must not be included in business reporting. Raw counts describe retained observations within caps; larger page parse totals appear as candidate_count in source checkpoints. Capped observations must not be called the complete directory population. Sites/emails require evidence; UNKNOWN history or non-ok MX cannot count as history-clean qualified organizations.

## 6. 测试和结束边界 / Tests and stopping boundary

```powershell
python -m unittest tests.test_brand_acquisition tests.test_brand_acquisition_offline tests.test_industry_directory_acquisition -q
python -m compileall -q .
git diff --check
```

完整测试须使用 repo-local 临时目录并按本阶段报告区分既有失败和新增回归。当前没有真实端到端结果，READY_FOR_PRODUCTION_REVIEW=false。获得真实证据后更新开发验收报告并独立审查，不自动提升 SAFE40，不修改 WorkBuddy/V1/V2/MX政策/V6话术，不写生产、不建发送计划、不连接SMTP、不发邮件、不部署。

Use repo-local temporary directories for the full suite and distinguish inherited failures from new regressions. There is no real end-to-end acceptance yet; READY_FOR_PRODUCTION_REVIEW=false. After real evidence is obtained, update development acceptance artifacts for separate review. Never automatically promote SAFE40, alter WorkBuddy/V1/V2/MX policy/V6 copy, write production, create send plans, connect SMTP, send email or deploy.

自检 / Self-check: 双语、执行/未执行边界、敏感信息、风险、下一步与非生产授权均已检查 / bilingual content, execution boundaries, sensitive information, risks, next steps and non-production authorization checked。
