# PHASE 4B.1E — 行业名录驱动获取 / Industry Directory Acquisition

## 结论 / Conclusion

已从指定的 4B.1D 基线开发独立行业目录扩展，完成离线解析、证据导入、分类、去重、官网候选交接、断点恢复及可移植验收入口。当前 `CODEX_SANDBOX_NETWORK_DISABLED=1`，没有执行真实目录抓取；真实组织、已验证官网和真实商务邮箱产量均为 0。工程离线交付完成，不代表已获得客户或可部署生产。

The isolated directory extension is built from the specified 4B.1D baseline. Offline parsing, evidence import, classification, deduplication, official-site candidate handoff, resumable checkpoints and the portable canary entry point are implemented. With `CODEX_SANDBOX_NETWORK_DISABLED=1`, no real directory capture was executed. Real organizations, verified sites and real business emails are all zero. Offline engineering delivery does not mean customer acquisition or production readiness.

```text
PHASE = 4B.1E
BASELINE_COMMIT = 99350124604a54b3457e34e2285bf4fb7ccdfe5d
BRANCH = codex/phase4b1e-industry-directory-acquisition
REMOTE_REPOSITORY = 1569032023yf-star/roktandrazo-outreach-codex
DIRECTORY_ADAPTERS_IMPLEMENTED = 3 primary + 1 conditional public-list parser
TOYFAIR_ADAPTER_READY = true (offline contract)
GCA_ADAPTER_READY = true (offline contract)
NYNOW_ADAPTER_READY = true (offline contract)
ASTRA_ADAPTER_STATUS = PUBLIC_ACCESS_UNVALIDATED; conditional offline parser ready
OFFLINE_PARSING_VALIDATED = true
LIVE_PAGES_FETCHED = 0
RAW_ORGANIZATION_RECORDS = 0
DEDUPED_CANDIDATE_ORGS = 0
RETAIL_BUYER_CANDIDATES = 0
BRAND_OWNER_CANDIDATES = 0
OFFICIAL_SITES_VERIFIED = 0
FIRST_PARTY_EMAILS_FOUND = 0
HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL = 0
LIVE_END_TO_END_VALIDATED = false
READY_FOR_PRODUCTION_REVIEW = false
```

## 实现与来源边界 / Implementation and source boundaries

| 来源 / Source | 实现 / Implementation | 证据边界 / Evidence boundary |
|---|---|---|
| Toy Fair | `toyfair_retailer_directory_adapter` | 2026 参会线索；buyer_type 保持 unverified / 2026 participation leads; buyer type remains unverified |
| GCA | `gca_brand_directory_adapter` | 区分 CARD_BRAND、CARD_PUBLISHER、PAPER_GOODS_BRAND、SUPPLIER、DISTRIBUTOR、UNKNOWN；供应商不自动进入品牌客户池 / Distinguishes member types; suppliers are not automatically brand prospects |
| NY NOW | `nynow_exhibitor_directory_adapter` | 产品类目筛选；保留 Summer2026 或显式历史年份 / Product-category filtering; preserves Summer2026 or explicit archive year |
| ASTRA | `astra_public_store_directory_adapter` | 仅可用的公开列表；当前可访问性未知，不声称已经获取 / Public lists only; accessibility is currently unknown, with no acquisition claim |

解析支持记录内语义字段、目录卡片、带表头的表格、受目录容器约束的列表，以及显式 Organization JSON-LD。测试结构为人工合成，不是已下载的真实页面，不能证明四个网站的当前 DOM 已兼容。无法识别的结构返回 PARSE_EMPTY，须在获准环境人工核对，不把导航名称当企业。

Parsers support record-scoped semantic fields, directory cards, header-based tables, lists within directory containers, and explicit Organization JSON-LD. Test structures are synthetic, not downloaded real pages; they do not certify compatibility with current live DOMs. Unrecognized structures return PARSE_EMPTY and require authorized review, rather than treating navigation labels as businesses.

目录分类使用 `organization_type` 保存七类候选/冲突口径，并保留 `directory_member_type`、国家、来源年份、来源类型、记录指纹及分类原因。明确美国标签优先；其他地区保留原文，不从名称推断国家。缺少品类的零售登记标记 needs_review；不相关品类和印刷生产供应商有可解释排除原因。

Directory classification uses `organization_type` for the requested candidate/conflict taxonomy and preserves member type, country, source year/class, record fingerprint and explanation. Explicit US labels receive priority; other geography remains verbatim. Names never imply country. Retail registrations without categories require review; irrelevant categories and printing suppliers retain explainable exclusions.

复用 `BrandCandidate`、现有官网候选解析器、capture manifest/import、`AcquisitionPipeline.run_sources`、官网身份匹配和第一方邮箱提取、只读 `HistoryChecker` 及既有 MX 回调。新增组织核验回调将第一方站点名称匹配记录为 `ORGANIZATION_CONFIRMED`；**不将零售商或目录品牌候选写成 BRAND_OWNER**，不证明品牌所有权、采购意向或发送同意。所有类型仍只是候选业务分类。

Reuses `BrandCandidate`, the official-site resolver, capture manifest/import, resumable `AcquisitionPipeline.run_sources`, official identity matching and first-party email extraction, read-only `HistoryChecker` and existing MX callbacks. The organization callback records first-party name corroboration as `ORGANIZATION_CONFIRMED`; **it does not label retailers or directory brand candidates as BRAND_OWNER** or establish ownership, buying intent or contact consent. Business classifications remain hypotheses.

网站链接仅来自同一组织记录内的显式证据；目录资料页和页面全局链接不自动视为企业官网。无链接保持 unresolved。未验证的同名企业跨来源保持独立；已验证相同官网域名合并并保留全部来源、采集 ID 和证据。不同已验证域名同名组织标记冲突并关闭联系资格。

Site links come only from explicit evidence within the same organization record. Directory profiles and global page links are not automatically official sites. Missing links remain unresolved. Unverified names across sources remain independent; identical verified domains merge while retaining all source URLs, capture IDs and evidence. Same-name organizations with distinct verified domains become conflicts with contact qualification closed.

导入和测试夹具仍是 discovery_only，不调用官网/邮箱/MX核验。来源标签不同的断点不会互相提升资格。真实目录组织仅在独立官网匹配、完整第一方邮箱证据、历史 new_candidate 和 MX ok 全部满足时达到 complete；历史 UNKNOWN、MX 异常、缺失时间戳或邮箱归属失败保持 pending/拒绝。本引擎不创建 SAFE、lead、发送权限或发送计划。

Imports and fixtures remain discovery-only and do not invoke site/email/MX qualification. Checkpoints with different provenance labels cannot elevate each other. Live directory organizations reach complete only after independent site matching, complete first-party email evidence, new_candidate history and MX ok. Unknown history, MX errors, missing timestamps or wrong email affiliation remain pending/rejected. This engine creates no SAFE records, leads, send permissions or send plans.

修正了共享捕获执行器中官方页面观察器将 `PageResult` 当字典读取的问题；新增模拟传输测试实际连通原有官网匹配、邮箱提取和证据记录器。这些模拟响应只存在临时测试目录，其计数不进入本报告的业务产量。

Fixed the shared capture runner's official-page observer reading `PageResult` as a dictionary. A mocked-transport integration test exercises the existing identity check, email extractor and capture recorder. These responses exist only in temporary test directories and never enter business-yield counts in this report.

## 漏斗与受控输出 / Funnel and controlled output

真实业务指标详见同目录 `PHASE4B1E_DIRECTORY_CANARY_RESULT.json`。四个渠道的 LIVE_PUBLIC_CAPTURE 和 OFFLINE_IMPORT 客户指标均为 0。单独的持久化合成重放包含 4 条 TEST_FIXTURE 记录：零售候选 2、品牌候选 2、显式网站候选 4；已验证官网、邮箱和可用客户均为 0。相同合成名称未因名称相似被合并。

Real business metrics are in `PHASE4B1E_DIRECTORY_CANARY_RESULT.json`. All four channels have zero LIVE_PUBLIC_CAPTURE and OFFLINE_IMPORT customer yield. The separate deterministic replay contains four TEST_FIXTURE records: two retail candidates, two brand candidates and four explicit site candidates, with zero verified sites, emails or qualified customers. Equal synthetic names are not merged by name similarity.

候选、页面原文、采集清单及断点只写入已核实被 Git 忽略的 `output/brand_acquisition/phase4b1e/`。已执行离线合成 capture → manifest → validate/import → parser → discovery-only checkpoint 重放。没有导入真实客户名单，没有访问生产数据库或使用生产凭据。

Candidates, page bodies, manifests and checkpoints are written only to the verified Git-ignored `output/brand_acquisition/phase4b1e/`. A synthetic capture → manifest → validation/import → parser → discovery-only checkpoint replay was executed. No real customer list was imported, and no production DB or credentials were used.

## 测试 / Tests

- 定向测试 / Targeted: 73/73 通过 / passed（既有 43 + 新增 30 / existing 43 + new 30）。四个来源均覆盖正常、空、结构变化、无官网、非美国、同名不同组织、验证后合并、错误邮箱、不安全导入、来源缺失和证据损坏。
- 完整测试 / Full suite: 449 项，435 通过、2 失败、12 错误 / 449 run, 435 passed, 2 failures, 12 errors。
- 历史失败 / Historical failures: `test_dashboard_consolidated.TestSourceAudit.test_archived_dashboards_have_disable_marker`；`test_inventory_followup.TestInventoryArchival.test_archived_scripts_have_disable_marker`。缺少被忽略的归档材料 / ignored archive materials are absent。
- 环境错误 / Environment errors: 7 个 `.env` 依赖模块导入错误、2 个 canonical authorization 测试的 sender import 错误、2 个 dev DB routing 子进程错误、1 个归档脚本目录缺失 / seven environment-dependent module import errors, two sender-import authorization errors, two development DB-routing subprocess errors and one missing archive-directory error。
- 基线比对 / Baseline comparison: 对照本地 4B.1D 完整日志（419 项、405 通过、2 失败、12 错误），失败/错误测试名称集合相同；新增代码回归 0 / failure and error name sets match the 4B.1D log (419 run, 405 passed, 2 failed, 12 errored); zero new-code regressions。
- 编译 / Compileall: `python -m compileall -q .` 通过 / passed。
- 差异 / Diff check: `git diff --check` 通过 / passed。
- 日志 / Logs: `output/brand_acquisition_test_tmp/phase4b1e_targeted.log`、`phase4b1e_full_suite.log`、`phase4b1e_full_suite_summary.json`，仅本地忽略目录 / local ignored output only。

一次通过 stdin 启动测试的诊断运行出现 Windows 子进程入口错误，引入额外 5 failures/1 error；已保留 `phase4b1e_stdin_bootstrap.log` 和 summary，并用与基线相同的 `python -c` 启动方式重跑。上方结果使用修正后的最终完整运行，未把该诊断运行当成新增业务代码回归。

A diagnostic run launched through stdin caused Windows child-process entry errors and added five failures/one error. Its log and summary are preserved as `phase4b1e_stdin_bootstrap.*`. The suite was rerun using the baseline's `python -c` launch method. Counts above refer to the corrected final full run; the diagnostic launch failure is not classified as a business-code regression.

## 未执行事项与后续 / Unexecuted work and next steps

未执行真实页面抓取、站点条款实时复核、ASTRA 公开权限核验、真实组织身份确认、真实邮箱和 MX 验收，也未提供获准开发历史副本。下一步仅在获准隔离开发环境按双语运行手册执行最多每来源 2 个目录页面的 canary，核对真实布局及来源证据。四来源时每来源最多 22 个原始候选，总计最多 88（不超过 90）；官网验证沿用原有每站页面预算。遇登录、挑战或限制即停止该来源。全套历史/环境错误仍须由相应维护任务处理。

No real pages were fetched, terms reviewed live, ASTRA public permissions checked, real identities/emails/MX accepted, or approved development history copy supplied. Next, run the bilingual canary runbook only in an authorized isolated development environment, capped at two directory pages per source, and review real layouts and provenance. With four sources, each retains at most 22 raw candidates, totaling at most 88 (below 90); official-site verification retains its existing per-site budget. Stop a restricted/login/challenge source. Historical/environment test failures remain for their respective maintenance tasks.

## 安全与提交口径 / Safety and commit reporting

```text
WORKBUDDY_CHANGED = false
PRODUCTION_DB_WRITES = 0
PRODUCTION_DEPLOYMENT = false
CANONICAL_INVENTORY_CHANGED = false
SAFE40_BATCH_CHANGED = false
V1_CHANGED = false
V2_CHANGED = false
MX_POLICY_CHANGED = false
SMTP_CONNECTIONS = 0
EMAILS_SENT = 0
SEND_PLANS_CREATED = 0
SEND_AUTHORIZATIONS_CREATED = 0
V6_TEMPLATES_CHANGED = false
```

报告在提交前生成，避免虚构其自身提交 SHA 或预先声明推送成功。准确 COMMIT_SHA、PUSH_SUCCESS 和远端分支 SHA 在提交并重新查询远端后由最终交付消息给出；可用运行手册的只读命令复核。提交范围仅为开发获取模块、测试和三份交付文件。

This report is generated before commit and does not fabricate its own commit SHA or predeclare push success. Exact COMMIT_SHA, PUSH_SUCCESS and remote branch SHA are supplied in the final delivery after commit and remote revalidation, and can be checked with the runbook's read-only commands. Commit scope is limited to development acquisition modules, tests and the three deliverables.

报告自检 / Report self-check: 中英内容、执行与未执行事项、风险与后续、无敏感名单/凭据、离线与真实指标分离、无未验收事项冒充完成均已检查 / bilingual content, executed/unexecuted work, risks/next steps, no sensitive lists/credentials, separate offline/live metrics, and no unvalidated completion claims checked。
