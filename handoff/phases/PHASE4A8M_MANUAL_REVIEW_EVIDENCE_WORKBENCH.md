# Phase 4A.8M 人工审核证据工作台 / Manual Review Evidence Workbench

## 改动前现状 / Pre-change workflow map

- 审核入口 / Review entry: `leads.review_reason_code` marks a lead for review; the localhost-only `bd_review_server.py` lists rows whose reason is nonempty. / `leads.review_reason_code` 标识待审线索；仅监听本机的服务器列出原因非空的记录。
- 原因 / Reasons: UI recognizes `CONTACT_ROLE_UNCERTAIN`, `WEAK_EVIDENCE`, `CONTACT_FORM_ONLY`, `OTHER_STATE_RETAIL`, `BOUNCE_REVIEW`, `DOMAIN_MISMATCH`, `MATURE_BRAND`, `COUNTRY_UNCERTAIN`, `POSSIBLE_DUPLICATE`, `EMAIL_SOURCE_UNCERTAIN`, `BUSINESS_FIT_UNCERTAIN`, `MANUAL_SEND_CANDIDATE`, `OTHER`; database may hold additional codes. / 界面识别上述 13 类，数据库可能还有其他原因码。
- 状态 / Status: default pending; approved_auto, approved_manual, rejected, deferred, and recheck_pending are used by the shared workflow. `review_created_at` records queue entry; `review_priority` controls high-first sorting, not eligibility. / 默认待审；共用流程还使用自动批准、手动批准、拒绝、延期及待复核状态。创建时间表示入队时间；优先级仅影响排序，不授予资格。
- 列表 API / List API: `/api/leads` returns identity, location, email/source, official site, evidence URL, confidence, lead/review status/reason/priority/times, notes, address/phone and queued Facebook status/URL/email. `/api/history` runs historical cross-check. / 列表接口返回上述线索字段及 Facebook 队列摘要；历史接口执行历史交叉核查。
- 写入和审计 / Writes and audit: approve_auto, approve_manual, reject, defer, recheck_official, recheck_facebook call `review_workflow.apply_review_action` and write `review_log`; approval may change send eligibility, while rejection/defer/recheck do not authorize sending. `submit_manual_email` requires a same-party live evidence page with literal email/snippet, history and A0 checks, then writes manual submission and review audit. / 六种现有操作走共用审核与日志；批准可能改变发送资格，其余操作不能授权发送。人工邮箱提交须经同主体真实页面、字面邮箱及片段、历史和 A0 校验，并写入审计。
- 已发现的既有风险 / Pre-existing risk found: `/api/manual-a0` accepts an email without evidence and sets `auto_sendable=1` after partial hard-block checks. This conflicts with the phase's no-guessed-email/no-gate-bypass requirement; remediation must route it through the validated manual-email workflow. / 旧 `manual-a0` 入口无需证据即可设置自动可发，与本阶段安全要求冲突；必须收敛到已验证的人工邮箱流程。

## 实施 / Implementation

- 在现有本机审核服务器上增加证据详情接口与九段式详情视图；浏览器工作按需触发，单次只运行一个后台任务。没有第二个审核应用或数据库迁移。/ Added a review-evidence API and nine-section detail view to the existing localhost server; browser work is on demand, with only one background job at a time. No second app or database migration.
- 证据模型只读组装线索、官网、结构化邮箱标记、4A.8K 遥测、审计、历史门禁和冻结 V1/V2 结果。MX 只读新鲜缓存；没有缓存时展示 UNKNOWN 并保持不合格，不现场查询 DNS。/ The read-only model assembles lead, official-site, structured-email flag, 4A.8K telemetry, audit, history gates and frozen V1/V2 results. MX reads fresh cache only; missing cache is UNKNOWN and fail-closed, with no live DNS query.
- Facebook 仅使用既存业务页面 URL 或经合格官网页面发现的链接；Playwright 使用开发目录内的持久 profile。遇登录、验证码或页面缺失，逐条软失败，不规避访问控制。官网直接链接必须由合格同主体页面重新验证，不能仅信任旧队列来源标签。/ Facebook uses only an existing business-page URL or a link found on an accepted official page; Playwright uses a persistent profile under the development root. Login, CAPTCHA and missing pages fail softly without bypass. Direct official linkage is reverified from an accepted same-party page rather than trusting an old queue label.
- 社交邮箱仅作人工证据，A/B/C 分类不创建收件人、不写邮箱、不提升 SAFE。找回官网动作转交既有官网页面验证和第一方邮箱提取函数，结果仅展示为待人工提交的证据。/ Social email is evidence only: A/B/C classification does not create a recipient, write an email or promote SAFE. The recovered-website action hands off to existing official-page verification and first-party extraction functions; its result remains review evidence until a validated manual submission.
- 接受或拒绝 Facebook 身份依据写入既有 `review_log`，记录前后相同的审核状态、理由、来源和 URL；不更新线索发送资格。旧 `/api/manual-a0` 改为委托 `submit_manual_email`，不再允许无证据直接提升。/ Accepting or rejecting Facebook identity evidence writes the existing `review_log` with unchanged review status, reason, source and URL; lead eligibility is untouched. The legacy `/api/manual-a0` now delegates to `submit_manual_email` and cannot directly promote an evidence-free address.

## 副本队列初筛 / Copy-only cohort screening

- 只读 SQLite 在线备份副本完整性 / Read-only-derived SQLite online-backup integrity: `ok`.
- 待审总量 / Pending manual review total: **599**.
- 历史或安全阻断排除 / History or safety-blocked excluded: **142**.
- 可恢复待审 / Potentially recoverable pending review: **457**.
- 高价值且已有 Facebook URL / High-value leads with an existing Facebook URL: **1**. Remaining bounded canary selection scans accepted public official homepages for direct Facebook links; it does not search Maps or Facebook. / 其余有界样本仅检查合格公开官网首页的直接 Facebook 链接，不搜索 Maps 或 Facebook。

## 验证 / Validation

- 新增 13 项离线合成数据库定向测试通过，覆盖历史排除、A/B/C 来源、可见邮箱、登录/验证码/缺页软失败、官网交接、证据审计、无证据 A0 拒绝及安全链接渲染。/ Thirteen new offline synthetic-DB targeted tests passed, covering history exclusions, A/B/C provenance, visible email, login/CAPTCHA/missing-page fail-soft paths, official-site handoff, evidence audit, evidence-free A0 rejection, and safe link rendering.
- 标准完整 `unittest discover -s tests`：最终运行通过，446 项，失败 0，错误 0。/ The final standard full unittest run passed: 446 tests, 0 failures, 0 errors.
- 前端 JavaScript 语法检查通过。/ Front-end JavaScript syntax check passed.

## 公开网页金丝雀 / Public-web canary

- 使用生产数据库的只读 SQLite 在线备份副本，完整性 `ok`；仅开发副本被读取，未运行 Inventory。/ Used an integrity-checked SQLite online-backup copy derived from production read-only; only the development copy was read, with no Inventory run.
- `CANARY_SELECTED=40`, `OFFICIAL_SITES_SCANNED_FOR_FB=39`, `FB_PAGES_ATTEMPTED=10`, `FB_PAGES_OPENED=10`。已有 Facebook URL 的高价值记录仅 1 条；其他页面来自合格官网首页的直接链接。/ Forty high-value leads were selected, 39 public official homepages scanned, and 10 Facebook business pages attempted and opened. Only one high-value lead had an existing Facebook URL; the others came from direct links on accepted official homepages.
- `FB_LOGIN_REQUIRED=0`, `FB_CAPTCHA=0`, `FB_PAGE_NOT_FOUND=0`, `FB_OTHER_ERRORS=0`。/ None of these browser error states occurred.
- `OFFICIAL_SITE_LINKED_FB_PAGES=10`, `STRONG_MATCH_FB_PAGES=0`; 9 个页面有字面可见的公开邮箱，均为 Class A；Class B/C 为 0。/ Ten pages met verified official-site linkage, none relied on Tier B alone; nine pages showed literal public emails, all Class A, with zero Class B/C emails.
- `FB_NEW_EMAILS_NOT_IN_DB=7`, `NEW_UNIQUE_ORGS_WITH_EMAIL=7`。这里“数据库中没有”的测量范围严格为 `leads.email`；尚未对新邮箱执行全部历史/抑制/退信/V1/V2/MX 门禁，因此它们只是潜在机会，绝非 SAFE。/ Seven email strings were absent from `leads.email`, across seven potentially recoverable organizations. The uniqueness comparison did not include every historical table; the newly observed addresses have not passed history, suppression, bounce, V1, V2 or MX gates. They are opportunities, never SAFE.
- `FB_WEBSITE_RECOVERED=0`, `FB_WEBSITE_VERIFIED=0`, `FB_TO_OFFICIAL_SITE_EMAIL_FOUND=0`。本样本没有验证 Facebook → 新官网 → 第一方邮箱的正向实证；该交接仅由确定性测试覆盖。/ This cohort did not provide a live positive Facebook → recovered website → first-party email case; that handoff is covered by deterministic tests only.
- 固定阈值结果 `HIGH_YIELD`（7 条相对 `leads.email` 新的 Class A 邮箱及 7 个潜在组织）。建议只评审有界高价值人工队列预取，绝不加入标准 Inventory；所有新邮箱仍需逐条走人工证据与既有资格门禁。/ Under the preset threshold, the result is HIGH_YIELD (seven Class A emails new relative to `leads.email` and seven potential organizations). Recommend only a bounded high-value manual-review prefetch for review; never add Facebook to canonical Inventory. Every address still requires manual evidence validation and existing gates.

## 安全与交接结论 / Safety and handoff decision

- `V1_CHANGED=false`, `V2_CHANGED=false`, `MX_CHANGED=false`, `HISTORY_RULES_CHANGED=false`, `SUPPRESSION_RULES_CHANGED=false`, `BOUNCE_RULES_CHANGED=false`。既有六种审核操作保留；唯一收窄是无证据的旧 A0 捷径。/ The six shared review actions remain; only the unsafe evidence-free legacy A0 shortcut was narrowed.
- `PRODUCTION_DB_WRITES=0`, `PRODUCTION_FILES_CHANGED=0`, `PRODUCTION_DEPLOYMENT=false`, `WORKBUDDY_CHANGED=false`, `MAX_PAGES3_CANARY_TOUCHED=false`, `INVENTORY_RUNS=0`, `SCHEDULER_CHANGES=0`, `SMTP_CONNECTIONS=0`, `EMAILS_SENT=0`, `FSP_CREATED=0`, `SEND_AUTHORIZATION_CREATED=0`。/ All listed production, scheduling and send-side effects were zero.
- 原始开发金丝雀聚合结果保存在忽略提交的 `output/phase4a8m_manual_review_facebook_canary.json`；可提交的去敏聚合副本在 `handoff/phases/PHASE4A8M_CANARY_RESULT.json`。浏览器 profile、cookies、数据库副本均不提交。/ The raw development aggregate is in ignored output; a sanitized aggregate copy is in handoff. Browser profiles, cookies and the database copy are not committed.
- `READY_FOR_PRODUCTION_REVIEW=true` 只表示可评审开发补丁，不表示部署许可或发送许可。/ Ready for production review means the development patch can be reviewed; it is not deployment or send authorization.

## 最终验收摘要 / Final acceptance summary

- `BASELINE_COMMIT=41bcb4f4bab35c490e48c6c2460b7c6e8af450dd`；`REVIEW_WORKFLOW_MAPPED=true`；`EXISTING_REVIEW_ACTIONS_PRESERVED=true`（旧无证据 A0 绕道被安全收窄）。/ Baseline and workflow mapping are confirmed; existing review actions remain, except the unsafe evidence-free A0 shortcut was narrowed.
- `EVIDENCE_WORKBENCH_IMPLEMENTED=true`；`OFFICIAL_SITE_PANEL_IMPLEMENTED=true`；`BLOCKER_MATRIX_IMPLEMENTED=true`；`FACEBOOK_EVIDENCE_PANEL_IMPLEMENTED=true`；`RECOVERED_WEBSITE_PANEL_IMPLEMENTED=true`。/ The workbench and all required panels are implemented.
- `MANUAL_REVIEW_TOTAL=599`；`HISTORY_BLOCKED_EXCLUDED=142`；`RECOVERABLE_MANUAL_REVIEW=457`。/ These are counts from the integrity-checked development DB copy.
- `CANARY_SELECTED=40`；`FB_PAGES_ATTEMPTED=10`；`FB_PAGES_OPENED=10`；`FB_LOGIN_REQUIRED=0`；`FB_CAPTCHA=0`；`FB_PAGE_NOT_FOUND=0`。/ These are the bounded public-web canary counts.
- `OFFICIAL_SITE_LINKED_FB_PAGES=10`；`FB_PUBLIC_EMAILS_FOUND=9`；`FB_NEW_EMAILS_NOT_IN_DB=7`（仅对比 `leads.email`）；`CLASS_A_EMAILS_FOUND=9`；`CLASS_B_EMAILS_FOUND=0`；`CLASS_C_EMAILS_FOUND=0`。/ Seven addresses were new relative only to `leads.email`, not verified against all historical or eligibility gates.
- `FB_WEBSITE_RECOVERED=0`；`FB_WEBSITE_VERIFIED=0`；`FB_TO_OFFICIAL_SITE_EMAIL_FOUND=0`；`NEW_UNIQUE_ORGS_WITH_EMAIL=7`（潜在，不是 SAFE）。/ No live recovered-website case was observed; seven organizations are only potential review opportunities.
- `FACEBOOK_YIELD_RESULT=HIGH_YIELD`；`FACEBOOK_PREFETCH_RECOMMENDED=true`（仅有界高价值人工审核队列）；`MANUAL_ON_DEMAND_FACEBOOK_RECOMMENDED=false`（可按需操作仍保留，但建议有限预取）。/ High yield supports bounded high-value review prefetch, not canonical Inventory; on-demand use remains available.
- `V1_CHANGED=false`；`V2_CHANGED=false`；`MX_CHANGED=false`；`HISTORY_RULES_CHANGED=false`；`SUPPRESSION_RULES_CHANGED=false`；`BOUNCE_RULES_CHANGED=false`。/ The listed eligibility and safety policies were unchanged.
- `TARGETED_TESTS=13 PASS`；`FULL_SUITE=446 PASS, 0 FAILED, 0 ERRORS`；`COMPILEALL=PASS`；`GIT_DIFF_CHECK=PASS`。/ Targeted and final complete tests, compilation, and whitespace/conflict checks passed.
- `FILES_CHANGED=bd_review_server.py, review_evidence_workbench.py, review_evidence_ui.js, scripts/phase4a8m_canary.py, tests/test_review_evidence_workbench.py, handoff/CURRENT_STATUS.md, handoff/LATEST_RESULT.json, handoff/CHANGELOG.md, handoff/phases/PHASE4A8M_MANUAL_REVIEW_EVIDENCE_WORKBENCH.md, handoff/phases/PHASE4A8M_CANARY_RESULT.json`。/ Only these development-code, test and handoff files form this phase.
- `READY_FOR_PRODUCTION_REVIEW=true`；`PRODUCTION_DEPLOYMENT=false`。/ Ready for review only; nothing was deployed.
