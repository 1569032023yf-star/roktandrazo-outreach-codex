# 4B.1G 官网与公开商务邮箱转化 / Official-site and public business-email conversion

44 个真实目录候选中，核实 **2 家官网**；其中 **1 家取得官网真实公开商务邮箱且 MX 通过**。没有获准开发历史副本，历史确认全新客户为 **0**。

Of 44 live directory observations, **two official sites** were verified; **one yielded a genuine public first-party business email and passed MX**. Without an approved development history copy, **zero customers are history-confirmed new**.

`RESULT=AUTHORIZED_WEB_OR_HISTORY_INPUT_REQUIRED`。官网与邮箱阶段已完成真实验证；历史输入仍缺失，整体历史资格链尚未完成。

The live official-site/email stage is validated. History input remains unavailable, so the complete qualification chain is not validated.

## 数量漏斗 / Conversion funnel

| 指标 / Metric | 含义 / Meaning | 数量 / Value |
| --- | --- | ---: |
| `INPUT_LIVE_DIRECTORY_CANDIDATES` | 真实目录记录 / Live directory observations | 44 |
| `ICP_RELEVANT_CANDIDATES` | 已有充分产品证据的目标候选 / ICP candidates supported by product evidence | 2 |
| `PUBLIC_SEARCHES_PERFORMED` | 实际公开搜索 / Actual public searches | 58 |
| `OFFICIAL_SITE_CANDIDATES_FOUND` | 候选网站URL（按原记录计） / Candidate site URLs per source record | 42 |
| `CANDIDATES_WITH_SITE_CLUES` | 有网站线索的记录 / Records with site clues | 35 |
| `OFFICIAL_SITES_VERIFIED` | 核实独立组织官网 / Verified official organization sites | 2 |
| `FIRST_PARTY_EMAILS_FOUND` | 取得公开官网邮箱的组织 / Organizations with first-party emails | 1 |
| `B2B_ROLE_EMAILS_FOUND` | 有B2B角色邮箱的组织 / Organizations with B2B role emails | 1 |
| `MX_OK` | 正式MX通过 / Formal MX passed | 1 |
| `HISTORY_SOURCE_AVAILABLE` | 获准历史副本可用 / Approved history copy available | false |
| `HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL` | 历史确认全新且有邮箱的组织 / History-clean unique organizations with email | 0 |
| `DUPLICATES_CONFIRMED` | 已确认重复记录 / Confirmed duplicate observations | 0 |
| `UNIQUE_ORGANIZATIONS_VERIFIED` | 经核实独立组织 / Verified unique organizations | 2 |
| `IDENTITY_CONFLICTS` | 确认身份冲突记录 / Confirmed identity conflicts | 0 |
| `TOYFAIR_VERIFIED_SITES` | Toy Fair 核实官网 / Verified sites | 1 |
| `TOYFAIR_FIRST_PARTY_EMAILS` | Toy Fair 官网邮箱 / First-party emails | 0 |
| `NYNOW_VERIFIED_SITES` | NY NOW 核实官网 / Verified sites | 1 |
| `NYNOW_FIRST_PARTY_EMAILS` | NY NOW 官网邮箱 / First-party emails | 1 |

这些是本轮证据支持的下限，尚未核实的记录不是已确认无官网或无邮箱。官网确认与候选分类不构成品牌所有权、采购意向或发信授权。

These are evidence-backed lower bounds. Unresolved records do not prove absence of a site or email. Site verification and candidate classification do not establish brand ownership, buying intent or sending permission.

## 真实来源与官网证据 / Source lineage and first-party evidence

- 基线 / Baseline: `20184f443e11a88f0ef1de95ac4d6f38740f1b86`；分支 / Branch: `codex/phase4b1g-official-site-email-conversion`。
- 原 4B.1F 的 4 个捕获和 44 个候选仍在，校验捕获 SHA-256、时区时间、来源 URL、记录指纹、名称与证据归属后直接复用；未扩展目录，也未重采 GCA/ASTRA。
- The four original 4B.1F captures and 44 observations were retained and reused after checking hashes, timezone timestamps, URLs, fingerprints, names and evidence lineage. No additional directory was acquired; GCA/ASTRA were not revisited.
- 输入指纹 / Input fingerprint: `cee7e9ae895fbd9b7671b05fe2a8432a9be247763b21f3f2ce48fa534cd653bd`。哈希验证完整性；原目录来源真实性未在本轮重新建立。官网身份另行通过本轮真实 HTTPS 获取验证。
- Hashes establish integrity; original-directory capture authenticity was not re-established in this phase. Official identity was independently checked against live first-party HTTPS responses.

| 已核实主体 / Verified organization | 官网 / Official site | 本轮结果 / Outcome |
| --- | --- | --- |
| Abrams Books / ABRAMS | https://www.abramsbooks.com/ | 自站主页链接 Logo 明确 Abrams Books，主标题 ABRAMS，About/Contact/retailer 内容提供出版与商务证据；公开官网邮箱 1，MX=ok，历史 UNKNOWN。 / Home-linked site logo and compatible primary title establish identity; About/Contact/retailer pages support the publishing and business context. One first-party email, MX=ok, history UNKNOWN. |
| A STORE OF FIRE AND DICE LLC | https://astoreoffireanddice.wordpress.com/ | 门店主页主体名、美国纽约地址与游戏产品一致；零售买家候选，未取得可接受公开邮箱。 / Matching self-name, New York address and gaming products support a retailer candidate; no acceptable public email found. |

每条记录保留目录来源、身份状态、官网、邮箱角色、证据 URL/原文/时间、HTTP/final URL、MX 与历史状态。真实邮箱及网页正文只留在 ignored 输出，不进入 Git。

Each record retains directory source, identity status, site, email role, evidence URL/excerpt/time, HTTP/final URL, MX and history status. Actual contact addresses and page bodies remain in ignored local output.

## 实现、访问预算与断点 / Implementation, access budgets and checkpoints

`SearchEvidenceAdapter` 导入实际公开搜索记录；搜索摘要、目录链接与任意 imported verified/email 字段只作为线索。只有默认真实 `PublicPageFetcher` 的第一方响应可进入 live 数量；测试夹具独立计数（本轮均为 0）。

`SearchEvidenceAdapter` imports observed public-search evidence. Snippets, directory links and imported verified/email claims remain clues. Only real first-party responses through the default `PublicPageFetcher` enter live metrics; fixtures are counted separately (zero in this live run).

身份核验结合官网主标题、自站首页链接 Logo、明确 DBA、国家与产品/主体内容。第三方产品标题、标题次级品牌分段、品牌/赞助商 Logo、隐藏脚本均不能自动证明归属。不猜域名，不拼邮箱，不使用摘要邮箱作官网证据。

Identity checks combine primary site title, home-linked site logo, explicit DBA, country and product/organization context. Third-party product titles, secondary brand segments, sponsor logos and hidden scripts cannot automatically establish ownership. Domains and emails are not generated, and snippet emails are not first-party evidence.

官网确认后复用 `_extract_email_evidence`、`audit_brand_email`、正式 `check_mx_cached` 与 `HistoryChecker`；未修改统一邮箱/MX门槛。批准历史副本缺失时，全部 44 条输出 `UNKNOWN`；旧断点清洁状态也重置为 UNKNOWN。

After identity verification, the stage reuses `_extract_email_evidence`, `audit_brand_email`, formal `check_mx_cached` and `HistoryChecker`; shared hygiene/MX policies are unchanged. All 44 history states remain UNKNOWN without an approved copy; previous clean checkpoint states are reset when that input is absent.

每候选最多 2 次搜索、3 个域名、12 次页面 fetch 调用；累积预算和停止域名写入断点，重跑不能重置。实际 HTTP 串行 1 worker（最大允许 4），浏览器未用（最大 1）。fetch 内部重定向不冒称独立计数的 wire 请求。

Budgets cap each candidate at two searches, three hosts and 12 page-fetch calls. Cumulative budgets and stopped hosts persist across resumes. HTTP uses one serial worker (authorized maximum four); no browser is used (maximum one). Internal redirects are not misreported as separately counted wire requests.

本轮累计 57 次 fetch 调用：14 ok、17 rate_limited、15 access_restricted、9 permanent_unavailable、2 network_error。31 个域名停止；4 个旧 HTTP 200 挑战响应已重新识别并从有效页面移除，原捕获保留作审计。18 个新捕获文件哈希均复核通过；捕获文件数不等于有效官网数。每候选最多实际 10 次调用，未超预算。

Across this run, 57 fetch calls produced 14 ok, 17 rate_limited, 15 access_restricted, nine permanent_unavailable and two network_error outcomes. Thirty-one hosts were stopped. Four previously accepted HTTP-200 challenge responses were reclassified and excluded while preserving raw captures. All 18 capture-file hashes were checked; capture count is not verified-site count. Maximum observed candidate usage was ten fetch calls.

44 条记录全部保留：2 条 reviewed、29 条 restricted、9 条 search_input_pending、4 条 network_or_identity_pending。42 条未确认记录独立保存到 manual_review.json。未知身份不编造排除理由。

All 44 observations remain: two reviewed, 29 restricted, nine search_input_pending and four network_or_identity_pending. Forty-two unresolved records are saved separately for manual review. Unknown identities are not assigned fabricated exclusion reasons.

按名称中的业务线索排序，最终 ICP 分类要求真实官网产品证据。域名、独立归属名称与国家一致才汇总；同域不同品牌不自动合并，确认同名不同域的冲突不计资格。本次确认重复 0、身份冲突 0，不代表未知主体之间不存在重复。

Name cues prioritize work; final ICP classification requires first-party product evidence. Group only matching host, independently attributed name and country. Do not automatically merge different brands sharing a domain, and exclude confirmed same-name/different-host conflicts. Zero confirmed duplicates/conflicts does not prove unresolved organizations are distinct.

## 测试与独立审查 / Testing and independent review

| 范围 / Scope | 总数 / Run | 通过 / Passed | 失败 / Failures | 错误 / Errors | 跳过 / Skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| 同启动方式基线 / Baseline with matching startup | 457 | 443 | 2 | 12 | 0 |
| 定向，旧81+新32 / Targeted, existing 81 + new 32 | 113 | 113 | 0 | 0 | 0 |
| 最终全套 / Final full suite | 489 | 475 | 2 | 12 | 0 |

`NEW_CODE_REGRESSIONS=0`。旧 443 个成功 ID 全保留，32 个新增 ID 全成功，失败/错误 ID 与基线完全一致。独立 Reviewer 最终未发现剩余身份阻断项；独立 Tester 采用无 .env、禁网、开发守卫和本地 TEMP/TMP。

All 443 baseline passing IDs remain, all 32 added IDs pass, and failure/error IDs exactly match the baseline. The independent Reviewer found no remaining identity blockers. The independent Tester used no .env, denied external networking, installed development guards and used local TEMP/TMP.

旧失败 ID / Retained failure IDs:

- `test_dashboard_consolidated.TestSourceAudit.test_archived_dashboards_have_disable_marker`
- `test_inventory_followup.TestInventoryArchival.test_archived_scripts_have_disable_marker`

旧错误 ID / Retained error IDs:

- `unittest.loader._FailedTest.test_bounce_pipeline`
- `unittest.loader._FailedTest.test_p0_runtime_semantics`
- `test_p1_canonical_send_chain.A3AuthorizationTest.test_missing_real_fsp_id_fails_closed`
- `test_p1_canonical_send_chain.A3AuthorizationTest.test_plan_entry_id_is_real_fsp_id_at_creation`
- `unittest.loader._FailedTest.test_phase2a_safety_mutex`
- `unittest.loader._FailedTest.test_phase4a1b_linked_backlog`
- `unittest.loader._FailedTest.test_phase4a1c_discovery_coexistence`
- `test_phase4a3o_dev_db_routing.Phase4A3ODevDatabaseRoutingTests.test_explicit_development_copy_is_preserved_after_env_loader`
- `test_phase4a3o_dev_db_routing.Phase4A3ODevDatabaseRoutingTests.test_explicit_temp_copy_is_preserved_after_env_loader`
- `unittest.loader._FailedTest.test_phase4a8d_access_unreachable_city_liveness`
- `unittest.loader._FailedTest.test_sender_transaction`
- `test_single_smtp_authority.TestSingleSmtpAuthority.test_archived_scripts_fail_closed`

这 14 个是本轮之前已有的失败/环境问题；全量并非全绿，未修改断言来掩盖问题。详细 traceback 与精确 ID 对照见 ignored testing/。

These 14 outcomes predate this phase. The full suite is not entirely green, and assertions were not weakened to hide failures. Tracebacks and exact ID comparison remain in ignored testing/.

复现命令 / Reproduction commands:

```powershell
python -X utf8 scripts/run_official_site_conversion.py --input-dir '../roktandrazo-outreach-4b1f/output/brand_acquisition/phase4b1f' --search-evidence output/brand_acquisition/phase4b1g/search/observations.json --authorized-live-web
python -X utf8 -c "import development_safety; development_safety.install(); import unittest; s=unittest.TestLoader().discover('tests', pattern='test_phase4b1g_site_conversion.py'); r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(not r.wasSuccessful())"
```

完整基线一致测试命令记录在 `output/brand_acquisition/phase4b1g/testing/current-testing-summary.md`，使用 `python -X utf8 -c` 启动，不能用 stdin 启动替代。

The complete baseline-consistent commands are recorded in the local bilingual testing summary and use `python -X utf8 -c`, not stdin startup.

## 生产边界 / Production boundaries

| 字段 / Field | 值 / Value |
| --- | --- |
| `PRODUCTION_DEPLOYMENT` | false |
| `PRODUCTION_DB_WRITES` | 0 |
| `WORKBUDDY_CHANGED` | false |
| `CANONICAL_INVENTORY_CHANGED` | false |
| `SAFE40_BATCH_CHANGED` | false |
| `V1_CHANGED` | false |
| `V2_CHANGED` | false |
| `MX_POLICY_CHANGED` | false |
| `SMTP_CONNECTIONS` | 0 |
| `EMAILS_SENT` | 0 |
| `SEND_PLANS_CREATED` | 0 |
| `SEND_AUTHORIZATIONS_CREATED` | 0 |
| `V6_TEMPLATES_CHANGED` | false |

新增模块只输出 JSON；正式 SMTP/IMAP 守卫保持，未调用发信、plan、授权或生产 DB 接口。Git 改动仅为本阶段模块、CLI、测试及两份脱敏报告；未改 Inventory/WorkBuddy/V1/V2/MX策略/V6模板。

The new module outputs JSON only. Existing SMTP/IMAP guards remain active, and send, plan, authorization and production-DB interfaces are unused. Git changes contain only this stage's module, CLI, tests and two redacted reports; Inventory/WorkBuddy/V1/V2/MX policy/V6 templates are unchanged.

## 交付与剩余输入 / Delivery and remaining input

已测试实现提交 / Tested implementation commit: `3ce322ab566ee3953bf7095adda4f6661db2a7c7`；该提交已正常 push，`ls-remote` 核实 SHA 一致。报告 JSON 的 COMMIT_SHA 指此实现提交。

The implementation commit was pushed and verified against `ls-remote`. COMMIT_SHA in the tracked JSON identifies that implementation commit.

报告随后的交付提交正常推送；包含报告的最终 HEAD 在 push 后写入 ignored `output/brand_acquisition/phase4b1g/delivery_receipt.json`，并在最终回复给出，避免 Git 提交自引用。

The subsequent documentation commit is also pushed. Its final documentation-inclusive HEAD is recorded after push in the ignored delivery receipt and final reply, avoiding a self-referential Git commit.

公开邮箱名单、原始搜索和捕获、断点、人工复核与测试日志均位于 `output/brand_acquisition/phase4b1g/`。后续历史资格需要获准开发历史副本；目前未读取 WorkBuddy 生产库，未向受限域名重试或绕过挑战。

Contacts, raw search/capture evidence, checkpoints, manual review and test logs remain in `output/brand_acquisition/phase4b1g/`. History qualification requires an approved development history copy. No WorkBuddy production database was read, and stopped hosts/challenges were not bypassed.
