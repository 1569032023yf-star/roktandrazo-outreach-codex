# PHASE 4A.3Q — 官网解析网络重试根因与窄修复 / Website Resolver Network-Retry Root Cause and Narrow Fix

## 结论 / Decision

本阶段在任何 Maps 或官网网络请求之前停止。原因不是安全护栏或运行时失败，而是“同一 10 条记录”这一强制 cohort 不能从新鲜生产副本中无歧义重建：当前代码按相同 linked-backlog 资格规则返回 18 条可处理记录，其中 **11** 条缺少官网；Phase 4A.3P 报告的是在其副本内先发生一次重复项官网回填后，只有 **10** 条进入 resolver。

This phase stopped before any Maps or merchant-site network request. The reason is neither a safety guard nor a runtime failure: the mandatory “same ten rows” cohort cannot be reconstructed unambiguously from a fresh production copy. The current code, using the same linked-backlog eligibility rules, returns 18 eligible rows, **11** without a website; the Phase 4A.3P report records **10** entering the resolver after one duplicate-website backfill occurred inside its now-deleted copy.

No resolver result was fabricated and no merchant was arbitrarily excluded. Therefore no root-cause claim or production-path fix is justified in this phase.

未伪造 resolver 结果，也没有任意排除商户。因此，本阶段不能对根因下结论，也不具备修改生产路径的依据。

## 安全与副本 / Safety and Copy

- A fresh SQLite online-backup copy of the authoritative production DB was created only under development quarantine; `PRAGMA integrity_check = ok`.
- 从权威生产 DB 创建了仅位于开发隔离目录的新鲜 SQLite online-backup 副本；`PRAGMA integrity_check = ok`。
- `PRODUCTION_DB_WRITES = 0`; `PRODUCTION_FILES_CHANGED = 0`; `REAL_SMTP_CONNECTIONS = 0`; `REAL_IMAP_CONNECTIONS = 0`; `SCHEDULER_CHANGES = 0`; `FROZEN_FILES_CHANGED = 0`.
- No full Inventory, Maps search, official-site fetch, V2/MX evaluation, PreSend, FSP, authorization, or deployment was run.
- 未运行完整 Inventory、Maps 搜索、官网抓取、V2/MX 评估、PreSend、FSP、授权或部署。

## 静态结构核查 / Static Structural Audit

| 项目 / Item | 已确认事实 / Confirmed fact |
|---|---|
| `CURRENT_CANDIDATE_LIMIT` | `10` |
| `MAX_DETAIL_VISITS` | up to `10` / 最多 `10` |
| `RESOLVER_DEADLINE_SECONDS` | `45` |
| Provider call | `provider.search_places(..., page_size=10)` |
| BrowserMaps behavior | collects up to ten cards, then opens each candidate detail page / 收集最多十张卡片，再逐一打开详情页 |
| Identity threshold | unchanged at `80` / 保持 `80` |

This establishes a structural deadline risk, but it does **not** establish that detail fan-out was the measured primary cause. The required identical-cohort runtime timing measurement did not run.

这证明存在结构性 deadline 风险，但**不能**证明 detail fan-out 是已测量的主因；要求的相同 cohort 运行时计时没有执行。

## Cohort Reconciliation Gate / 队列对账门槛

| 指标 / Metric | 结果 / Result |
|---|---:|
| Fresh-copy linked-backlog eligible / 新副本可处理积压 | 18 |
| Fresh-copy no-website rows / 新副本缺官网记录 | 11 |
| Phase 4A.3P resolver attempts / P 阶段 resolver 尝试 | 10 |
| Difference / 差异 | 1 |
| Exact ten identity known / 精确十条身份可确认 | `false` |

Historical handoff evidence explains the difference but does not identify its exact row: Phase 4A.3P recorded `DUPLICATE_WEBSITE_BACKFILLED = 1` before linked-backlog processing, while the current fresh copy correctly retains the pre-rehearsal source state. The historical Phase 4A.3J report likewise documented an eleven-row no-website cohort. Because the P copy and its row-level selection artifact were intentionally removed after the rehearsal, choosing ten from the eleven now would be an unapproved, non-deterministic data decision.

历史交接证据解释了差异，但没有标明确切记录：Phase 4A.3P 在 linked-backlog 前记录 `DUPLICATE_WEBSITE_BACKFILLED = 1`，而当前新副本正确保留演练前的源状态。更早的 Phase 4A.3J 报告同样记录了 11 条无官网 cohort。P 阶段副本及逐行选择制品在演练后已按安全要求清除；如今从 11 条中挑选 10 条将是未经授权、非确定性的数据决定。

## 未执行项目 / Not Run

| Required measurement / 要求测量 | Status / 状态 | Reason / 原因 |
|---|---|---|
| Exact-ten resolver reproduction / 精确十条 resolver 重现 | `NOT_RUN` | cohort identity mismatch / 队列身份不匹配 |
| Three-row timing diagnosis / 三条计时诊断 | `NOT_RUN` | same reason / 同上 |
| Narrow fix / 窄修复 | `NOT_JUSTIFIED` | no runtime proof / 无运行时证据 |
| Same-cohort after comparison / 同队列修复后对比 | `NOT_RUN` | no justified fix / 无合理修复 |
| Known-positive controls / 已知正样本 | `NOT_RUN` | no justified fix / 无合理修复 |
| Targeted/full tests / 定向/全套测试 | `NOT_RUN` | no source change / 未改源码 |

## Required Next Authority / 所需下一步授权

`CURRENT_BLOCKER = COHORT_PROVENANCE_GAP`.

Before any network reproduction, an explicit choice is needed: either (1) authorize a deterministic eleven-row measurement and update the acceptance cohort to eleven, or (2) provide/authorize a durable row-level manifest identifying the exact ten Phase 4A.3P records. Do not infer the missing identity from business names, do not run Inventory, and do not loosen resolver, V2, MX, or evidence policy.

在任何联网重现之前，需要一个明确选择：（1）授权对确定性的 11 条记录进行测量，并将验收 cohort 更新为 11；或（2）提供/授权建立一份可持久保存的逐行 manifest，明确 Phase 4A.3P 的精确 10 条记录。不得从商户名称推断缺失身份、不得运行 Inventory、不得放宽 resolver、V2、MX 或证据策略。

## Final Fields / 最终字段

```text
ATTEMPTS = 0
ROOT_CAUSE_NETWORK_RETRY = NOT_MEASURED (COHORT_PROVENANCE_GAP)
PROVIDER_TIMEOUT = NOT_MEASURED
MAPS_NAVIGATION_TIMEOUT = NOT_MEASURED
SOCKET_NOT_CONNECTED = NOT_MEASURED
OTHER = NOT_MEASURED
DETAIL_FANOUT_IS_MEASURED_PRIMARY_CAUSE = NOT_PROVEN
AFTER_RESOLVED = NOT_RUN
AFTER_NETWORK_RETRY = NOT_RUN
AFTER_NOT_FOUND = NOT_RUN
AFTER_IDENTITY_REVIEW = NOT_RUN
KNOWN_POSITIVE_EXPECTED_DOMAIN_MATCHES = NOT_RUN
KNOWN_POSITIVE_WRONG_DOMAIN_MATCHES = NOT_RUN
WEBSITE_RESOLUTION_BLOCKER_FIXED = false
PRODUCTION_FILES_IN_PATCH = none
TARGETED_TESTS = NOT_RUN (no source change)
FULL_SUITE = NOT_RUN (no source change; prior baseline 354 passed + 76 subtests)
FAILED = 0 (no test execution in this phase)
ERRORS = 0 (no test execution in this phase)
V2_POLICY_CHANGED = false
MX_POLICY_CHANGED = false
READY_FOR_ONE_FINAL_INVENTORY_AFTER_FIX = false
```
