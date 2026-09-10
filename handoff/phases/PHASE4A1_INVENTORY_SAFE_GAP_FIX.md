# Phase 4A.1 Inventory SAFE-gap 窄修复审计 / Narrow-fix audit

## 决策 / Decision

触发请求第7节 STOP：428条待补库空邮箱中166条没有linked staging。未开始源码修改、未新增管线、未运行生产或副本Inventory、未部署。既有Phase4A验收结果不撤销；本次窄补丁尚未就绪。
Section 7 STOP is triggered: 166 of 428 replenishment empty-email leads lack linked staging. No source changes, new pipeline, production/copy Inventory run, or deployment occurred. Prior Phase 4A acceptance remains historical fact; this narrow patch is not ready.

## 复现 / Reproduction

从开发 bd_orchestrator.py 的 stage_inventory AST 取原始 remaining==0 分支，在隔离环境执行：
BROAD_READY=34, TARGET=30, remaining=max(0,30-34)=0。
原始分支返回true，并调用 finish_job_run('offline-reproduction','completed',actual=34,gap=0)。不读取SAFE。
The unchanged remaining==0 branch was extracted from the development stage_inventory AST and executed in isolation. With BroadReady=34 and target=30, it returns true and records completed/actual=34/gap=0 without consulting SAFE.

结合Phase4A实测日志（completed，BroadReady34/30）与最终冻结MX/V2结果（SAFE=1），BUG_REPRODUCED=true。这是原始分支的离线复现及已存在真实运行证据，不是再次执行Inventory。
Together with recorded Phase4A completion at BroadReady34/30 and frozen SAFE=1, BUG_REPRODUCED=true. This is an offline canonical-branch reproduction plus prior live evidence, not another Inventory run.

源码定位 / Source locations:
- bd_orchestrator.py:487 remaining uses broad_ready.
- bd_orchestrator.py:490–493 immediately completes.
- bd_orchestrator.py:604–614 repeats BroadReady-based accounting.

## 副本与统计口径 / Copy and counting scope

仅以mode=ro读取生产源，通过SQLite online backup创建开发副本；integrity_check=ok。所有审计查询只读副本。 / Production source was read mode=ro for an online backup; integrity_check=ok. Audit queries used the read-only copy.
COPY = _audit_quarantine/phase4a1/20260910T061244Z/audit_copy.db
副本及原始审计JSON被Git忽略，不上传。 / The copy and raw audit JSON are Git-ignored and not uploaded.

EMPTY_EMAIL_LEADS_TOTAL = 482
EMPTY_EMAIL_WITH_OFFICIAL_WEBSITE = 100
EMPTY_EMAIL_WITH_LINKED_STAGING = 262
EMPTY_EMAIL_WITH_LINKED_STAGING_AND_WEBSITE = 7
EMPTY_EMAIL_WITHOUT_STAGING = 220

“WITH_LINKED_STAGING_AND_WEBSITE”要求该linked staging自身website非空，不能把lead网站静默视为staging已接通。 / This website count requires a nonempty website on the linked staging row; a lead website alone does not prove the staging route is connected.

| 全量空邮箱状态 / All empty-email status | Count |
|---|---:|
| manual_review_needed | 398 |
| contact_form_pool | 51 |
| new | 29 |
| sent | 3 |
| approved_manual_send | 1 |

482−51(contact_form_pool)−3(sent)=428，精确解释用户口径；并非断言生产新增54条。
482 minus 51 contact-form and three sent records equals the user's 428; this is a scope difference, not a claim of 54 new production records.

在428口径内 / Within the 428 scope:
- linked staging = 262
- without linked staging = 166

全部220条无关联记录中93条有官网；21条可在staging找到同名同城市州行，但仅是待审匹配线索，未证明同物理门店/组织。另199条没有这种精确名称城市州匹配。
Of all 220 unlinked records, 93 have websites. Twenty-one have staging rows with identical name/city/state, but these are review hints, not proof of physical-location or organization identity. The other 199 lack even that exact match.

## 已存在但未接通的资产 / Existing disconnected assets

STAGING_STATUS_DISTRIBUTION_FOR_EMPTY_EMAIL_LEADS:
manual_review_needed = 259
review_recovery = 3

run_staging_postprocess只选择当前active_city_id且状态为website_lookup_pending、email_extraction_pending、validation_pending、history_check_pending。上述262条当前直接消费数为0。
run_staging_postprocess only selects the active city and four pending statuses above. None of the 262 linked rows is directly consumable in its current state.

run_website_resolution可以选择当前城市、无website的manual_review_needed，成功后置为email_extraction_pending。这使部分无官网记录已有间接通道；但已有网站的manual_review_needed和review_recovery不能靠此查询重入。
run_website_resolution can take same-city manual_review_needed rows without websites and set email_extraction_pending on success. This indirectly connects some missing-site rows, but not existing-site manual-review rows or review_recovery rows.

三个具体缺口 / Three concrete gaps:
1. 166/428待补库lead没有linked staging，现有consumer以staging为入口而非扫描leads。 / 166 of 428 have no linked staging; the consumer takes staging, not leads.
2. 已有官网/失败重试记录的状态未进入安全consumer白名单。 / Existing-site and failed-retry statuses do not enter the safe consumer allowlist.
3. 消费限定active city，需要明确跨城市积压选择与限额，不能静默全库跑。 / Consumption is active-city scoped; cross-city backlog selection/budgets require explicit scope, not silent full-DB processing.

现有_upsert_result服务真实provider result；本次没有把旧lead伪造为新的发现结果，也未修改raw_payload或解除历史阻断。
Existing _upsert_result handles actual provider results. No old lead was forged into a new discovery result, raw payload modified, or history block removed.

## 旧扫描器审计 / Legacy scanner audit

inventory_monitor_executor.py:
- 271 onward: EMAIL_RE directly over raw HTML, no validated visible-text provenance.
- 405/422/440/469: synthetic "Email ... found ..." snippets, not literal page excerpts.
- 444: curl -k disables TLS verification.
- 702: another internal caller still exists; file must not be deleted.

这些发现确认不能仅用SAFE计数替换BroadReady，然后放行旧while-loop。旧扫描结果不能重标为official_page_visible，也不能成为SAFE权威。本阶段没有调用旧scanner。
These findings prohibit simply replacing BroadReady with SAFE while activating the legacy loop. Legacy output must not be relabeled official_page_visible or treated as SAFE authority. No legacy scanner ran this phase.

LEGACY_HTTP_SCANNER_MUST_NOT_BECOME_SAFE_AUTHORITY = true
LEGACY_SCANNER_USED_AS_SAFE_AUTHORITY = false

## 正确完成信号与目标 / Completion signal and targets

拟采用未改变的select_candidates_for_plan_v2/campaign_eligible_v2返回候选，按非空organization_key计唯一组织为SAFE_READY_UNIQUE_ORGS；不得创建FSP/授权。BroadReady仅信息指标。尚未实施。
The proposed source is unchanged frozen V2 selection, counting unique nonempty organization_key values as SAFE_READY_UNIQUE_ORGS without creating plans or authorizations. BroadReady remains informational. This is not implemented yet.

INVENTORY_TARGET=30 weekday / 工作日；周末既有逻辑60。
NEW_OUTREACH_TARGET=40。
30与40的差异单独报告；本次不更改目标、quota、窗口或发送政策。
The 30/40 mismatch is reported separately; targets, quota, windows and send policy are unchanged.

## 验证与下一步 / Validation and next step

BUG_REPRODUCED = true
BROADREADY_FALSE_COMPLETION_FIXED = false
PATCH_FILES = []
FULL_SUITE_PASS = NOT_RUN_THIS_PHASE
FROZEN_FILES_CHANGED = 0
SAFE_READY_BEFORE = NOT_MEASURED_THIS_PHASE
SAFE_READY_AFTER = NOT_RUN
READY_FOR_CONTROLLED_PRODUCTION_PATCH = false
PRODUCTION_WRITES = 0
SMTP_CONNECTIONS = 0
IMAP_CONNECTIONS = 0

最近已完成的Phase4A SAFE结果为1，仅历史参考，不冒充本次新测量。由于明确STOP条件，本阶段没有新增回归、重跑全套或受控Inventory；不能把历史312项通过写成本次通过。
Latest completed Phase4A SAFE was one, historical only. The explicit STOP prevented implementation, new regression tests, full-suite rerun and controlled Inventory; historical 312 passing tests are not presented as a current run.

请求先审查积压到现有staging的接入规则：允许范围、物理身份验证、原记录来源标记、可重试状态及active-city限制。批准后优先在bd_orchestrator.py与必要的discovery_service.py内重连，若需超过两源文件再次停止审查；不建第二套管线。
Review backlog-to-existing-staging routing rules first: scope, physical identity checks, original-source labeling, retryable statuses and active-city limits. After approval, prefer reconnecting within bd_orchestrator.py and, if necessary, discovery_service.py; stop again if more than two source files are needed. No second pipeline.
