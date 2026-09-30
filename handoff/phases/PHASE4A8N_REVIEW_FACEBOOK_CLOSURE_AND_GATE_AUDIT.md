# Phase 4A.8N 人工审核 Facebook 闭环与资格审计 / Review Facebook Closure and Gate Audit

## 范围与基线 / Scope and baseline

- `BASELINE_COMMIT=fde9110b916ee34f12b344736926675b43d5a138`。本阶段只更改开发仓库，未部署生产、运行 Inventory、改动 WorkBuddy 或调度。/ This phase changed only the development repository; it did not deploy, run Inventory, or change WorkBuddy or scheduling.
- 生产数据通过 SQLite `mode=ro` 在线备份到 `data/phase4a8n_copy.db`，副本 `PRAGMA integrity_check=ok`；原始逐条网页/邮箱记录只保存在被忽略的开发 `output/` 中，不进入 Git。/ Production data was online-backed up from SQLite read-only mode into a development copy with integrity `ok`; individual web/email observations remain only in ignored development output, never Git.

## 审核台发现闭环 / Review UI discovery closure

- `REVIEW_UI_FACEBOOK_AUTO_DISCOVERY_IMPLEMENTED=true`；`CANARY_AND_UI_DISCOVERY_PATH_UNIFIED=true`。新共享函数 `discover_official_facebook_candidates()` 仅对已验证同主体官网首页执行一次有界检查，筛选合法商家页 URL，规范化、去重并仅自动选择第一个官网直接链接候选；其他候选只供人工查看。审核台与金丝雀均调用它。/ The shared function verifies one same-party official homepage, extracts valid business-page URLs, normalizes and deduplicates them, and automatically selects only the first direct official link. Other candidates are for human review. Both the review UI and canary use this function.
- 审核台仍优先使用现存 URL；没有 URL 时才从官网发现。后台任务一次只运行一个，不阻塞本机审核服务器。明确区分官网缺失、官网未验证、官网无链接、非法 Facebook URL、登录、验证码、缺页和其他浏览器错误。/ The UI still prefers an existing URL, discovers from the official site only when absent, runs one background browser job at a time, and distinguishes the listed failure modes.
- 同一原 40 条有界选择逻辑重放，`REVIEW_UI_DISCOVERY_REPRODUCED=9`（要求至少 3）；40 条中 10 条实际打开 Facebook 页面，9 条为无预存 URL 的审核台发现路径。8 条合格官网没有 Facebook 链接，22 条官网无法通过本次静态验证；未搜索 Maps、Google 或 Facebook。/ On the same bounded 40-lead selection, nine no-prestored-URL cases completed the actual review-server backend path (minimum three); ten Facebook pages opened in total. Eight accepted sites had no link and 22 sites did not verify in this static probe. There was no Maps, Google, or Facebook search.
- Facebook 邮箱继续只是审核证据：`safe_eligible_from_social=false`，不写 `leads.email`、`auto_sendable`、资格、收件人或发送计划。旧 `/api/manual-a0` 继续委托证据完整的 `api_manual_email()`；接受 Facebook 身份只写审核日志。/ Social emails remain review evidence only, with no lead-email, sendability, recipient, or plan mutation. The legacy A0 endpoint still delegates to the validated manual-email path; identity acceptance writes only the audit log.

## 七候选完整审计 / Complete audit of seven candidates

- `MANUAL_REVIEW_TOTAL_REFERENCE=599`；`RECOVERABLE_MANUAL_REVIEW_REFERENCE=457`；`CLASS_A_CANDIDATES_RECONSTRUCTED=7`。七个候选均来自重新打开的官网直接关联 Facebook 业务页，具有公开可见完整邮箱及新鲜证据；“新”最初只相对 `leads.email`。/ The seven reconstructed Class A observations have literal visible public emails and fresh, officially linked business-page evidence; initial novelty was only against `leads.email`.
- 逐条复用 `history_crosscheck.cross_check`、`broad_ready._load_db_signals`、现行邮箱卫生、组织历史、现行 MX 路径以及冻结 V1/V2，只在副本/内存候选视图中计算；MX 只查询候选公开域名，无生产缓存写入。/ Per-candidate checks reused canonical history, broad-ready signals, hygiene, organization history, MX, and unchanged V1/V2, using only a copy/in-memory candidate view. MX queried public domains only, with no production-cache write.
- `HISTORY_CLEAN=7`；`MX_PASS=7`；`UNIQUE_ORG=7`。这三个单项通过不能代替整体资格。/ All seven passed these individual checks, but that does not establish overall eligibility.
- 互斥主桶 / Exclusive primary buckets: `POLICY_ONLY_BLOCKED=0`, `HISTORY_BLOCKED=0`, `MX_BLOCKED=0`, `SUPPRESSION_OR_BOUNCE_BLOCKED=0`, `IDENTITY_OR_EVIDENCE_BLOCKED=0`, `OTHER_BLOCKED=7`；`CLASS_A_READY_EXCEPT_POLICY=0`。五个候选仍有 `contact_form_only` 阻断，两个有第三方邮箱域阻断，其中一个同时属于两类；另一个候选的现行函数返回通过但来源政策未获批准。/ Five have a contact-form-only blocker, two a third-party email-domain blocker, with one overlap. The remaining candidate returned a pass from current functions despite an unapproved social source.
- `CURRENT_V1_PASS=1`；`CURRENT_V2_PASS=1` **仅为未写库的假设候选视图计算结果，不是 SAFE**。原因：现行 `_is_official_evidence()` 对同域邮箱/证据 URL 有回退路径，V2 也可能据此给未知 `official_site_linked_facebook` 来源 E1；正式白名单并无该来源。此现行政策边界必须单独评审，本阶段不修改 V1/V2，也不把该候选提升。/ One hypothetical candidate passed current V1 and V2 because existing same-domain/evidence-URL fallback can classify an unapproved social source. This is **not** a SAFE record or approval; the provenance policy requires separate review. No V1/V2 policy was changed.
- `OFFICIALLY_LINKED_FACEBOOK_POLICY_REVIEW_WARRANTED=false`，因为严格定义的 `CLASS_A_READY_EXCEPT_POLICY=0`，未达到至少 3 的决策阈值。Facebook 仍为人工审核辅助。/ Strict policy-only-ready count is zero, below the threshold of three; Facebook remains a manual-review aid.
- 去敏逐条门禁在 `PHASE4A8N_CLASS_A_GATE_AUDIT.json`：只使用匿名候选编号与布尔/状态/阻断，不含邮箱、商户名、Facebook URL、组织键或浏览器会话。/ The machine-readable audit uses anonymous candidate references and gate outcomes only, excluding addresses, business names, URLs, organization keys, and browser sessions.

## 累计生产评审包 / Cumulative production-review bundle

- `REQUIRES_4A8K=true`。4A.8M/4A.8N 的官网交接调用新版 `_extract_email_evidence(pages, business_name)`，审核台显示 4A.8K 遥测；结构化第一方邮箱类型需要 `campaign_eligible.py` 的 4A.8K 白名单。不能单独把审核台代码部署在旧生产 `discovery_service.py` 上。/ The review workbench depends on the 4A.8K extractor and telemetry; the structured first-party type depends on its V1 allowlist. Do not deploy the review files alone against the old production discovery module.
- `REQUIRED_4A8K_FILES=discovery/discovery_service.py, campaign_eligible.py`。/ These are the required 4A.8K code files.
- `PRODUCTION_REVIEW_BUNDLE_FILES=discovery/discovery_service.py, campaign_eligible.py, bd_review_server.py, review_evidence_workbench.py, review_evidence_ui.js`，恰好五个代码文件；不包含测试、脚本、handoff、数据库、开发安全文件或浏览器 profile。/ The cumulative review bundle consists of exactly these five code files, excluding tests, scripts, reports, databases, development guards, and browser profiles.
- 已只读核对：前三个既存生产文件与 Git `641b36b87af596a503cdcb8fb518eab66d5ffbb9` 的 blob 完全一致；后两文件当前生产不存在。`bounce_pipeline.py` 的 4A.8I 后续差异不在本包。`bd_orchestrator.py`、V2、Preflight、sender、daily_session、final_send_plan、outreach_control、provider、城市队列、scheduler 均不在本包。/ Read-only comparison confirms the three existing production files match the cited deployed Git baseline; the two helper/UI files are new. The unrelated bounce change and all listed frozen/operational files are excluded.

| 文件 / File | 生产基线 SHA-256 / Production baseline | 目标 SHA-256 / Target | 操作 / Action |
|---|---|---|---|
| `discovery/discovery_service.py` | `D23C760AEA14C995D859E709ACF898CE8E691DD70B129DF2F4B920D9E9617D07` | `865EA0BCF420AE77B2FBF371AE11967606CA659B19EFE419A62DF8150BAEC3CE` | replace / 替换 |
| `campaign_eligible.py` | `641B588350212DBF4768F5F224A55240C94857E9837C49B863DC6060F6A1B247` | `4E6C87822C74BF75AA7950FC1E5CC052AD119BE3BC0578252077839B36114B36` | replace / 替换 |
| `bd_review_server.py` | `B386940B0B7792FD183A976FB3C3920BB0AA631F68D54A416E49D23EE6F3A69D` | `F5941DF623037974E7C6DEECC5701BF5F4C7110805B8FB957043C5E252DD5CC4` | replace / 替换 |
| `review_evidence_workbench.py` | NEW / 新文件 | `70F02006F10B0B01DED705383917C04B23225B18F42D71EE9FC18599DE6B2BE9` | add / 新增 |
| `review_evidence_ui.js` | NEW / 新文件 | `6F3960AA6409898EA00337642E462CD624CD096DD99CB5AB151E0E082FD39402` | add / 新增 |

## 安全、测试与决定 / Safety, tests, and decision

- `MANUAL_A0_BYPASS_CLOSED=true`；`FACEBOOK_IDENTITY_ACCEPT_CHANGES_SEND_ELIGIBILITY=false`。/ The evidence-free A0 bypass remains closed and Facebook identity acceptance leaves send eligibility unchanged.
- `V1_CHANGED=false`, `V2_CHANGED=false`, `MX_POLICY_CHANGED=false`, `HISTORY_RULES_CHANGED=false`, `SUPPRESSION_RULES_CHANGED=false`, `BOUNCE_RULES_CHANGED=false`。/ These policies were not changed in this phase.
- `PRODUCTION_DB_WRITES=0`, `PRODUCTION_FILES_CHANGED=0`, `PRODUCTION_DEPLOYMENT=false`, `WORKBUDDY_CHANGED=false`, `MAX_PAGES3_CANARY_TOUCHED=false`, `INVENTORY_RUNS=0`, `SCHEDULER_CHANGES=0`, `SMTP_CONNECTIONS=0`, `EMAILS_SENT=0`, `FSP_CREATED=0`, `SEND_AUTHORIZATION_CREATED=0`。/ All listed forbidden side effects remained zero or false.
- `TARGETED_TESTS=20 PASS`；`FULL_SUITE=453 PASS, 0 FAILED, 0 ERRORS`；`COMPILEALL=PASS`；`JS_SYNTAX=PASS`；`GIT_DIFF_CHECK=PASS`。/ Twenty targeted tests and all 453 full-suite unittest cases passed with zero failures or errors; Python compilation, JavaScript syntax, and the Git diff check passed.
- `READY_FOR_PRODUCTION_REVIEW=true`，仅表示五文件累计包和现行规则风险可供人工评审；`READY_FOR_DEPLOYMENT=false`。/ Ready for human review of the five-file cumulative package and current-rule risk only, not for deployment.

## 本阶段文件清单 / Phase file inventory

- `FILES_CHANGED=bd_review_server.py, review_evidence_workbench.py, review_evidence_ui.js, scripts/phase4a8m_canary.py, tests/test_review_evidence_workbench.py, handoff/CURRENT_STATUS.md, handoff/LATEST_RESULT.json, handoff/CHANGELOG.md`；`FILES_ADDED=scripts/phase4a8n_reconstruct.py, scripts/phase4a8n_gate_audit.py, handoff/phases/PHASE4A8N_REVIEW_FACEBOOK_CLOSURE_AND_GATE_AUDIT.md, handoff/phases/PHASE4A8N_CLASS_A_GATE_AUDIT.json`。/ These are the development files changed and added in this phase; no production files were edited.
- `COMMIT_SHA` 与 `PUSH_SUCCESS` 以本次 Git 结果为准，不预填成功。/ The commit SHA and push result are reported from Git, never assumed in advance.
