# Phase 4A.8O 联系表单状态与证据来源边界 / Contact-form State and Evidence-source Boundary

## 基线与范围 / Baseline and scope

- `BASELINE_COMMIT=92ddc0843abce98bac4b2b969c00cd57cc41bb79`。仅开发实现及生产数据库只读来源副本审计；无生产部署、Inventory、邮件发送、调度或 WorkBuddy 变更。/ Development-only implementation and audit on a read-only-derived production DB copy; no production deployment, Inventory, sending, scheduling, or WorkBuddy change.
- `CONTACT_FORM_STALE_STATE_BUG=true`；`CONTACT_FORM_STATE_FIX_IMPLEMENTED=true`。原 `broad_ready._is_contact_form_only()` 优先读取旧 `status=contact_form_pool`，即使已填入真实邮箱仍判“仅表单”。`production_adapter`、`review_workflow` 与审核列表也存在相同派生状态问题。修复后只有当前无邮箱才会由历史表单状态产生该阻断；邮箱本身仍须通过全部独立门禁。/ The previous broad-ready predicate and related adapter, workflow, and UI paths could keep a lead form-only after an email was present. The corrected predicate treats historical form state as form-only only while no email is currently present; every separate email gate still applies.
- 生产副本的 `leads` 只有 `contact_form_url`，没有持久化的 `contact_form_only` 列；人工邮箱成功写入既有流程已设置 `status=new`。故无迁移、无批量数据清理，也不删除有价值的 `contact_form_url`。/ The copied production schema has `contact_form_url` but no persisted `contact_form_only` column, and successful manual-email submission already sets `status=new`. No migration or bulk cleanup is required; the contact URL remains intact.

## 状态生命周期 / State lifecycle

- `CONTACT_FORM_STATE_WRITERS`: `discovery/discovery_service.py` 为无邮箱但有联系表单的发现记录设置 `status=contact_form_pool`/`review_reason_code=contact_form_only`，并在成功提取官方邮箱时写入邮箱、来源、证据和新状态；`manual_email_workflow.py` 在有证据的人工邮箱成功分支写邮箱、来源、官网验证、`status=new`、审核状态和 `auto_sendable`；`review_workflow.py` 写人工决定和发送资格。/ Discovery creates form-pool state for no-email contact forms and updates official-email evidence; manual-email submission and review workflow write approved email and review/sendability state.
- `CONTACT_FORM_STATE_READERS`: `broad_ready.py`、`production_adapter.py`、`review_workflow.py`、`lead_hygiene_gate.py`、V1/V2、`bd_review_server.py` 列表与 `review_evidence_workbench.py` 门禁矩阵。/ These modules read or derive form-only state for readiness, hygiene, campaign eligibility, and review display.
- `CONTACT_FORM_STATE_CLEARERS`: `manual_email_workflow.py` 与 discovery 成功邮箱路径将状态转出 form pool；此次核心判定还可容忍旧状态未清，因为当前邮箱优先。/ Successful manual-email and discovery paths update status; the new predicate also tolerates stale state by giving current email precedence.

## 官方证据来源决策树 / Official evidence-source decision tree

- `UNAPPROVED_SOURCE_CAN_BYPASS_ALLOWLIST_BEFORE=true`；`UNAPPROVED_SOURCE_CAN_BYPASS_ALLOWLIST=false`（修复后）；`EVIDENCE_SOURCE_BOUNDARY_FIX_IMPLEMENTED=true`。修复前同域企业邮箱无需运行官方证据检查；免费邮箱以及 V2 Tier 的回退可以接受同域邮箱或非目录证据 URL。修复后 V1 对所有邮箱先检查明确来源类型，未批准来源加 `evidence_source_not_approved`；V2 继承 V1 阻断，不能据独立 Tier 推升资格。/ Previously, same-domain business email could skip official-evidence evaluation and legacy fallbacks could classify an unapproved source. V1 now blocks explicit unapproved provenance for every mailbox; V2 inherits that blocker and cannot promote it via Tier.
- `OFFICIAL_EVIDENCE_EXPLICIT_ALLOWLIST=official_page_visible, official_mailto, first_party_structured_data, wholesale_vendor_page, web_search_official`。/ These remain explicitly approved.
- `OFFICIAL_EVIDENCE_EXPLICIT_DENYLIST=all explicit non-allowlisted and non-legacy source types`，包括 `official_site_linked_facebook`, `facebook_social`, `social_only`, `third_party_directory`, `web_search_directory`, `web_search`, `search_snippet`, `guessed_email`, `manual_lookup`, `contact_form_only`。没有将 Facebook 加入允许名单。/ Explicit non-approved types fail closed; Facebook remains unapproved.
- `OFFICIAL_EVIDENCE_FALLBACK_PATHS`: 仅空来源和已识别历史兼容来源 `legacy`, `unknown`, `manual_verified`, `inventory_recovery`, `website_extracted` 可以沿用既有严格同域证据 URL 或邮箱域回退。对免费邮箱仍需第一方证据；对跨域企业邮箱仍维持原硬阻断。/ Existing first-party URL/domain fallbacks remain only for empty or identified legacy provenance; free mailboxes still need first-party evidence and cross-domain business addresses remain blocked.
- 生产副本历史来源分布审计发现 `unknown` 大量存在，故未采用“所有非白名单类型一律拒绝”的粗粒度方案。/ The historical copy contains many `unknown` provenance rows, so a blanket non-allowlist rejection would have harmed legacy compatibility.

## 同七候选复审 / Same-seven-candidate re-audit

- 复用 4A.8N 原始七条候选观察、同一开发副本及先前 MX 实测值；不再访问 Facebook、Maps、商户站点或 DNS。`CLASS_A_CANDIDATES_REAUDITED=7`；`HISTORY_CLEAN=7`, `MX_PASS=7`, `UNIQUE_ORG=7`。/ Reused exactly the prior seven observations, copy, and measured MX statuses, without new web or DNS traffic; all seven remain clean on these individual gates.
- `CONTACT_FORM_ONLY_BEFORE=5`, `CONTACT_FORM_ONLY_AFTER=0`, `CONTACT_FORM_STALE_BLOCKS_REMOVED=5`；`THIRD_PARTY_DOMAIN_BLOCKED=2`；`SOURCE_POLICY_BLOCKED=7`；`OTHER_BLOCKED=0`。两条跨域归属不因表单修复或 Facebook 身份而获批准。/ Five stale form blockers cleared, two cross-domain ownership blockers remain, and all seven are correctly blocked by the unapproved source policy.
- `CLASS_A_READY_EXCEPT_POLICY=5`；`CURRENT_V1_PASS=0`, `CURRENT_V2_PASS=0`。五条仅供下一阶段政策评审，不是 SAFE，不写线索邮箱或发送资格。`OFFICIALLY_LINKED_FACEBOOK_POLICY_REVIEW_WARRANTED=true` 仅表示达到“至少三条仅差政策”阈值，**并非批准**。/ Five are ready except for source policy and warrant a separate policy review, but none is SAFE or eligible under current V1/V2.
- 逐条 `CONTACT_FORM_STALE_FIXED` 是回顾性标记，不作为最终主桶；五条进入 `A_POLICY_ONLY_BLOCKED`，另两条进入 `C_THIRD_PARTY_DOMAIN_BLOCKED`。/ Per-candidate `CONTACT_FORM_STALE_FIXED` is a retrospective marker, not a final exclusive bucket; five end in policy-only and two in cross-domain buckets.
- 去敏逐条结果：`PHASE4A8O_SEVEN_CANDIDATE_REAUDIT.json`，只含匿名编号、布尔门禁、阻断与汇总，不含邮箱、商户名、Facebook URL 或凭据。/ The machine-readable report contains anonymous references and gate outcomes only.

## 生产历史副本资格漂移 / Production-history-copy eligibility drift

- 新鲜只读 SQLite 在线备份副本完整性 `ok`；618 条有邮箱线索进入有界、只读计算。旧语义以本次两处被修正的旧判定复现，新的判定在同一副本与同一 MX 输入上计算。此回放不是 Inventory 或发送计划。/ A fresh online SQLite backup passed integrity check. The old two predicates and new predicates were compared on the same 618 email-bearing leads and identical MX input; this was not Inventory or plan creation.
- `BROAD_READY_TOTAL_BEFORE=64`, `BROAD_READY_TOTAL_AFTER=80`；`V1_ELIGIBLE_TOTAL_BEFORE=53`, `V1_ELIGIBLE_TOTAL_AFTER=27`。V1 净减少 26 全部来自显式 `guessed_email`，没有误阻旧 `unknown` 来源；广义就绪增加由陈旧联系表单状态解除。/ Broad readiness rose by 16. All 26 V1 losses came from explicit guessed-email provenance, not historical `unknown` records.
- `V2_SAFE_UNIQUE_ORGS_BEFORE=0`, `V2_SAFE_UNIQUE_ORGS_AFTER=0`，但本副本没有 24 小时内 MX 缓存（`FRESH_MX_CACHE_DOMAINS=0`）；本次为**缓存限定、缺失即 DNS_ERROR**的保守回放，不能将 0 误称为实时 MX 证明。另以明确标注的合成 `MX=ok` 做资格漂移压力对照，V2 组织数 `27→27`，预期范围外变化为 0；这个 27 **不是 SAFE 库存**。相同输入下 `UNEXPECTED_BROAD_READY_DRIFT=0`, `UNEXPECTED_V1_DRIFT=0`, `UNEXPECTED_V2_DRIFT=0`。/ The copy had no fresh MX cache, so V2 remained zero under cache-only fail-closed replay; this is not a live-MX assertion. A separately labeled synthetic MX=ok policy stress test yielded 27→27 organizations with zero out-of-scope changes; 27 is **not** SAFE inventory. Unexpected drift was zero under the stated matched-input scopes.

## 累计生产评审包与安全 / Cumulative production-review bundle and safety

- `REQUIRES_4A8K=true`。`PRODUCTION_REVIEW_BUNDLE_FILES=discovery/discovery_service.py, campaign_eligible.py, bd_review_server.py, review_evidence_workbench.py, review_evidence_ui.js, broad_ready.py, production_adapter.py, review_workflow.py, campaign_eligible_v2.py`。后四个是本阶段修复联系表单判定、适配器与审核流程/候选选择所必需，不能从累计包中隐藏；这只是评审清单，**未部署**。/ The cumulative review bundle contains nine production code files, including the four newly required state and V2 selection files. It is a review manifest only, not a deployment.
- `MANUAL_A0_BYPASS_CLOSED=true`, `FACEBOOK_IDENTITY_ACCEPT_CHANGES_SEND_ELIGIBILITY=false`；`FACEBOOK_SOURCE_POLICY_CHANGED=false`, `V2_POLICY_RELAXED=false`, `MX_POLICY_CHANGED=false`, `HISTORY_RULES_RELAXED=false`, `SUPPRESSION_RULES_RELAXED=false`, `BOUNCE_RULES_RELAXED=false`。V2 唯一改动是让有邮箱的旧 form-pool 行进入既有正式门禁，未放宽 MX、证据或发送政策。/ The A0 bypass stays closed and Facebook identity acceptance never changes sendability. V2 changed only the form-pool candidate filter so an email-bearing historical row reaches existing gates; no MX, evidence, or send-policy relaxation occurred.
- `PRODUCTION_DB_WRITES=0`, `PRODUCTION_FILES_CHANGED=0`, `PRODUCTION_DEPLOYMENT=false`, `WORKBUDDY_CHANGED=false`, `MAX_PAGES3_CANARY_TOUCHED=false`, `INVENTORY_RUNS=0`, `SCHEDULER_CHANGES=0`, `SMTP_CONNECTIONS=0`, `EMAILS_SENT=0`, `FSP_CREATED=0`, `SEND_AUTHORIZATION_CREATED=0`。/ All forbidden production, scheduling, and sending side effects remained zero or false.
- `READY_FOR_PRODUCTION_REVIEW=true`，`READY_FOR_DEPLOYMENT=false`。仍需人工评审新增资格核心文件、V1 的 26 条 guessed-email 拒绝及缓存限定 V2 回放。/ Ready for human review of the expanded qualification-core patch and measured changes, never for deployment.

## 测试与提交 / Tests and publication

- `TARGETED_TESTS=59 PASS`（状态/资格相关 39 项 + 审核台 20 项）；`FULL_SUITE=463 PASS`、`FAILED=0`、`ERRORS=0`；`COMPILEALL=PASS`；`JS_SYNTAX=PASS`；`GIT_DIFF_CHECK=PASS`。/ Fifty-nine targeted tests passed across two module groups; the full suite passed 463 tests with zero failures/errors. Python compilation, JavaScript syntax, and the Git diff check passed.
