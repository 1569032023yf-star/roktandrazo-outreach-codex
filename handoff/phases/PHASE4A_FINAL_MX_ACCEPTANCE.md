# Phase 4A 最终 MX/V2 验收 / Final MX/V2 acceptance

验收通过；未恢复调度。 / Acceptance passed; scheduling was not resumed.

完成时间 / Completed UTC: 2026-09-10T02:29:18.009157+00:00
部署 run id / Deployment run id: phase4a-prod-20260910T020401Z

## 范围和方法 / Scope and method

仅执行一次联网 post-run measurement。初次前置断言在发出任何 MX 请求前停止：原 SQL 大小写敏感计数为91，冻结域名归一化后为90。只读核实当前与此前快照的域名集合完全相同，再测量90个唯一域名，没有扩大范围。
Exactly one networked post-run measurement ran. An initial precondition stopped before any MX request because the prior case-sensitive SQL counted 91 strings while frozen normalization yields 90 domains. Read-only comparison verified identical current and prior sets; 90 unique domains were measured without expanding scope.

调用生产未修改的 select_candidates_for_plan_v2（内部 campaign_eligible_v2），保留既有 query_mx Worker/DNS fallback。只读 Python profile 观察原函数返回值，不替换函数、不更改逻辑；对1085复用同次MX结果执行冻结review，没有第二次MX或Inventory。生产数据库以mode=ro打开。
The unchanged production select_candidates_for_plan_v2 and campaign_eligible_v2 were used with the existing query_mx Worker/DNS fallback. A read-only Python profile observed original return values without replacing functions or changing logic. Lead 1085's frozen review reused the same MX results; no second MX pass or Inventory ran. The production DB was opened with mode=ro.

## 结果 / Results

| 指标 / Metric | 数值 / Value |
|---|---:|
| RAW_DOMAIN_STRINGS | 91 |
| DOMAINS_CHECKED | 90 |
| MX_OK | 32 |
| MX_NXDOMAIN | 51 |
| MX_NULL | 0 |
| MX_NO_ROUTE | 7 |
| MX_DNS_ERROR | 0 |
| V2_ELIGIBLE_UNSENT | 1 |
| SAFE_FSP_UNIQUE_ORGS | 1 |
| SAFE_FSP_BEFORE | 0 |
| SAFE_FSP_AFTER | 1 |
| SAFE_FSP_UNIQUE_ORG_DELTA | 1 |

统计反映冻结路径真实返回值；没有为了提高通过数量放宽规则。SAFE数量是只读资格及组织去重结果，并未物化正式 Final Send Plan。
Counts reflect actual frozen-path results, without weakened rules. SAFE is read-only eligibility with organization deduplication, not a materialized Final Send Plan.

## Instant Replay Sports / 指定商户

lead_id = 1085
MX_PASS = true
V2_PASS = true
SAFE_FSP_ELIGIBLE = true
TIER = E1
MX_RESULT = ok
BLOCKERS = []

官方可见邮箱证据通过，时区 RESOLVED/America/New_York，组织键存在，证据新鲜；所有冻结 V2 检查通过。
Official visible-email evidence passed, timezone is RESOLVED/America/New_York, organization key is present, evidence is fresh, and all frozen V2 checks passed.

## 安全核验 / Safety verification

REAL_SMTP_CONNECTIONS = 0
REAL_IMAP_CONNECTIONS = 0
FINAL_SEND_PLAN_CREATED = 0
AUTHORIZATION_CREATED = 0
SCHEDULER_CHANGES = 0
FROZEN_FILES_CHANGED = 0
SCHEDULING_RESUMED = false
PHASE4A_INVENTORY_VALIDATION_PASS = true

五个冻结文件在测量前后SHA一致。发送、退信、抑制、正式FSP、授权及授权条目表计数前后一致；运行中设置邮件调用阻断审计，未触发。未修改任何代码文件、端点或逻辑。
All five frozen hashes matched before and after. Send, bounce, suppression, formal FSP, authorization and authorization-entry counts were unchanged. Mail-call blocking audit recorded no attempts. No code file, endpoint or logic was changed.

Windows PreSend/Outreach仍Disabled，WorkBuddy Inventory/PreSend/Preflight/Outreach仍PAUSED（只读复核）；未恢复任何调度。
Windows PreSend/Outreach remain Disabled and WorkBuddy Inventory/PreSend/Preflight/Outreach remain PAUSED, verified read-only. No scheduling was resumed.

本报告取代部署报告中“SAFE AFTER待测”的暂态结论；部署报告保留过程历史。详细逐域名输出留在Git忽略的隔离目录，仅将汇总交接上传GitHub。
This report supersedes the deployment report's temporary pending SAFE AFTER conclusion while preserving its history. Per-domain output remains in Git-ignored quarantine; only summarized handoff is uploaded.

NEXT_ACTION = STOP; await Ian's separate resume approval / 停止，等待 Ian 单独批准恢复调度
