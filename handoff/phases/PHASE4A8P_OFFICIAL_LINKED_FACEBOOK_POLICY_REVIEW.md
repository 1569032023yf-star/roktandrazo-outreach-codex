# Phase 4A.8P 官网直链 Facebook 商家页证据政策评审 / Official-site-linked Facebook evidence policy review

## 结论与范围 / Decision and scope

- `BASELINE_COMMIT=04bcde7034939f8d7b47f5061aed4c929c09c6f3`；`POLICY_RECOMMENDATION=KEEP_MANUAL_REVIEW_ONLY`；`POLICY_CANDIDATE_PASS=false`；`DEVELOPMENT_POLICY_IMPLEMENTED=false`。本阶段仅政策审计、离线夹具与新鲜生产数据库只读来源副本核对；不批准新来源，不部署或发送。/ This phase audits policy using offline fixtures and a fresh read-only-derived production copy. It does not approve a new source, deploy, or send.
- 五条历史 Class A 候选均为同域企业邮箱；另外两条为未证明归属的跨域企业邮箱。本批没有免费邮箱的真实正例。4A.8O 正式资格仍为七条全部拒绝。/ All five historical policy-only candidates are same-domain business mailboxes; the other two are unproven cross-domain business mailboxes. There is no real free-mail positive in this cohort, and formal V1/V2 still reject all seven.
- **核心缺口**：去敏观察保存了官网发现页 URL、Facebook URL、抓取时间、可见摘录和身份信号，但不是可重放的页面证据包；本阶段没有重新抓取并核验官网仍直接链接该页、Facebook 当前仍可公开访问且邮箱仍可见。因此历史五条不能计作通过现行可重新验证证据合同的真实正例，也不能满足 Section I 的 `CURRENT_5_RECOVERED>=3`。/ Historical fields are useful observations, not a replayable current proof that the verified official page still links the business page and the rendered public mailbox remains visible. Zero of the five meet a newly revalidated formal evidence contract in this phase; the required real recovery threshold is not met.

## 严格来源合同 / Narrow source contract

- 候选名称仅为 `official_site_linked_facebook`。官网须先通过现行 HTTPS/HTTP/TLS/同主体和商家身份核验；官网合格页面须直接包含该 Facebook 商家页 URL；Facebook 必须由普通公开浏览器可访问，不能来自搜索、目录、手贴 URL、登录绕过或挑战绕过。拒绝 `/login`, `/share`, `/sharer`, `/dialog`, `/profile.php`, `/people/` 及非商家页。/ Only a currently verified official page may directly link a public Facebook business page. Search, directory, pasted URLs, access-control bypasses, and personal/non-business paths are excluded.
- 必需字段：`official_website`, `official_link_source_url`, `facebook_page_url`, `facebook_page_fetched_at`, `visible_email`, `visible_email_excerpt`, `identity_match_signals`, `official_site_direct_link=true`。摘录必须逐字包含邮箱；直接链接之外至少一个独立身份信号。完整页面重验证及证据关联应由未来专用验证器执行，不能单靠 `email_source_type` 字符串。/ A future dedicated validator must recheck source-page linkage, public rendered visibility, literal excerpt, and an independent identity signal. Source-type text alone can never grant eligibility.
- 同域企业邮箱可作为最窄规则候选；免费邮箱只有在上述合同全部满足时才值得进一步评审，不能从本批推断真实误判率；跨域企业邮箱保持拒绝，Facebook 自述不构成企业域归属机制。/ Same-domain mail is the narrowest possible category. Free mail requires separate real validation; cross-domain business mail remains rejected absent independent domain ownership proof.
- 建议接口 `validate_official_site_linked_facebook_evidence(lead, evidence, now, fetcher) -> {valid, reasons, rechecked_at}`：先对官网与来源页执行现行官方站和身份校验，重新提取精确 Facebook 商家页 URL；然后用普通公开浏览器读取该页渲染文本，核对 URL 类型、主体独立信号、完整邮箱逐字摘录、时间上限与邮箱域类别。任何必填字段缺失、当前页面变化、网络失败或证明不足均返回 `valid=false`；V1/V2 只能消费 `valid=true` 的结果，不能直接相信来源字符串。此接口**仅为设计，未在生产资格代码中实现**。/ Proposed validator re-fetches the verified official source page and public rendered business page, then checks the exact link, independent identity, literal mailbox excerpt, age, and domain class. Missing, changed, unreachable, or ambiguous evidence fails closed. This is a design only, not qualification code.

## A/B/C 比较及指标口径 / Policy comparison and metric scope

下列混淆矩阵仅为**条件式离线场景**，不是真实世界独立裁定的真值：五条历史同域候选按合同完整的假设建模，另加一条合成免费邮箱正例；负例由两条历史跨域类别加十条合成挑战组成。真实五条未做当前页面复验，正式恢复数为 0。详细去敏矩阵在 `PHASE4A8P_POLICY_MATRIX.json`。/ The matrices are conditional offline scenarios, not independently adjudicated empirical outcomes. Formal real-candidate recovery is zero.

| 方案 / Policy | TP | FP | TN | FN | 五条条件式命中 / Conditional current-five hits | 两条跨域恢复 / Cross-domain recovered | 结论 / Result |
|---|---:|---:|---:|---:|---:|---:|---|
| A：仅同域 / Same-domain only | 5 | 0 | 12 | 1 | 5 | 0 | `NOT_PASS`：实际证据合同未复验 / Real contract unverified |
| B：同域+免费 / Same-domain + free | 6 | 0 | 12 | 0 | 5 | 0 | `NOT_PASS`：免费邮箱只有合成正例 / Free-mail evidence only synthetic |
| C：扩展跨域 / Cross-domain extension | 0 | 0 | 12 | 6 | 0 | 0 | `NOT_SAFE_TO_AUTOMATE`：无独立企业域归属机制 / No independent enterprise-domain mechanism |

对三个方案的离线挑战：`UNAPPROVED_SOCIAL_ACCEPTED=0`, `WEAK_IDENTITY_ACCEPTED=0`, `SEARCH_DISCOVERED_FB_ACCEPTED=0`, `PERSONAL_PAGE_ACCEPTED=0`, `CROSS_DOMAIN_UNPROVEN_ACCEPTED=0`。这些是测试模型结果，不是生产运行结果。反例包括未批准来源、搜索/目录发现、弱身份、个人页、不可见邮箱、缺字段、官网不再链接和过期证据；其中十条挑战为**合成**，不能冒充真实页面。/ All five hard-negative acceptance counts are zero in the offline model; ten adversarial cases are explicitly synthetic, not real pages.

## 自动与人工模式 / Automatic versus human-confirmed mode

- 自动模式吞吐较高，但一旦官网链接、页面邮箱或主体发生变化，旧证据可能在审计间隔内失效；必须先实现可重验合同及撤销机制，之后仍须过历史、抑制、退信、卫生、MX、组织唯一性和 V1/V2，绝不等于发送授权。/ Automatic qualification improves throughput but needs a replayable validator, revocation, and all downstream gates; it never authorizes sending.
- 推荐 `RECOMMENDED_HUMAN_CONFIRMATION=true`：审核员先复核当前官网直链、公开页面、独立身份和可见邮箱，再单独批准证据；`ACCEPT_FACEBOOK_IDENTITY` 只能确认身份，不可直接修改邮箱资格。当前仍只作为人工审核证据。/ Recommend human confirmation of the current link, page, identity, and visible mailbox. Identity approval alone must not alter send eligibility; current evidence remains review-only.
- 建议 `RECOMMENDED_FACEBOOK_EVIDENCE_MAX_AGE_DAYS=30`。对 30/60/90 天做离线边界比较：31 天时 30 天规则拒绝，而 60/90 天规则仍接受旧资料；因页面、邮箱及官网链接会变化，选择较短的 30 天，但过期前仍须在官网撤链、页面打不开、邮箱消失、名称明显不符或官网变化时立即失败关闭。/ Thirty days is the cautious maximum; 60/90 would accept older mutable social-profile data. Any broken link, inaccessible page, removed mailbox, identity mismatch, or official-site change must revoke eligibility immediately.

## 全副本漂移与边界保留 / Full-copy drift and retained boundaries

- 新鲜 SQLite 在线备份副本 `PRAGMA integrity_check=ok`；618 条有邮箱线索接受同一代码、同一 MX 输入的前后对照。`V1_BEFORE=27`, `V1_AFTER=27`, `V2_BEFORE=0`, `V2_AFTER=0`, `NEWLY_ACCEPTED_BY_SOURCE_TYPE={}`, `UNEXPECTED_V1_DRIFT=0`, `UNEXPECTED_V2_DRIFT=0`, `GUESSED_EMAIL_ACCEPTED=0`。因本阶段**没有**正式政策实现，前后相等；不能将其当成新增政策的安全证明。/ The fresh copy has 618 email-bearing leads and zero qualification-code drift because no policy was implemented. This does not validate a future policy.
- `FRESH_MX_CACHE_DOMAINS=0`，V2 使用缺失即 `dns_error` 的相同缓存限定输入，无 DNS 请求；V2=0 不是实时 SAFE 库存断言。/ There was no fresh MX cache; V2 zero is a matched fail-closed replay, not a live SAFE inventory assertion.
- `CONTACT_FORM_STATE_FIX_PRESERVED=true`, `EVIDENCE_SOURCE_BOUNDARY_FIX_PRESERVED=true`；现行 `facebook_social`, `social_only`, `search_snippet`, `third_party_directory`, `guessed_email` 继续拒绝；旧空/历史来源兼容与 4A.8O 的来源阻断保持原样。/ Existing contact-form and source-boundary fixes remain intact; no forbidden social or guessed source was approved.
- 生产评审包仍为 4A.8O 九文件清单：`discovery/discovery_service.py`, `campaign_eligible.py`, `bd_review_server.py`, `review_evidence_workbench.py`, `review_evidence_ui.js`, `broad_ready.py`, `production_adapter.py`, `review_workflow.py`, `campaign_eligible_v2.py`。本阶段新增的测试/脚本/报告不属于部署包。/ The cumulative production review bundle is unchanged from 4A.8O; phase test, script, and report artifacts are excluded.

## 安全与测试 / Safety and tests

- `PRODUCTION_DB_WRITES=0`, `PRODUCTION_DEPLOYMENT=false`, `WORKBUDDY_CHANGED=false`, `MAX_PAGES3_CANARY_TOUCHED=false`, `INVENTORY_RUNS=0`, `SMTP_CONNECTIONS=0`, `EMAILS_SENT=0`, `FSP_CREATED=0`, `SEND_AUTHORIZATION_CREATED=0`。/ No production, scheduling, Inventory, send, or authorization side effect occurred.
- `TARGETED_TESTS=8 PASS`，包含 A/B/C、同域/免费/跨域、未批准来源、缺字段、弱身份、不可见邮箱、过期及 30/60/90 天边界；`FULL_SUITE=471 PASS`、`FAILED=0`、`ERRORS=0`；`COMPILEALL=PASS`, `JS_SYNTAX=PASS`, `GIT_DIFF_CHECK=PASS`。4A.8O 既有 contact-form 与来源边界回归包含于全套。/ Eight targeted fixture tests and the full 471-test suite passed with zero failures/errors; compilation, JavaScript syntax, and diff checks passed. The full suite includes the prior contact-form and source-boundary regressions.
- `READY_FOR_PRODUCTION_REVIEW=false`（作为**新增 Facebook 正式来源政策**）；`READY_FOR_DEPLOYMENT=false`。仍可人工评审设计与既有 4A.8O 代码包，但不得把模拟矩阵当作政策批准。/ Not ready to promote a new Facebook provenance policy. The design and existing 4A.8O bundle may be reviewed, but simulation is not approval.
