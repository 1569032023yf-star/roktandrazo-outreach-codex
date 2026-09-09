# 分阶段修复计划 / Prioritized Remediation Plan

日期 / Date: 2026-09-08。本文件是计划，不是生产变更授权。 / This is a plan, not authorization to change production.

中文：第一阶段交付已完成：完整开发复制、隔离、静态运行图、写入/发送入口索引、只读数据证据与六份双语报告。未进行广泛重构。首个业务开发目标是 SAFE lead replenishment，保留五文件、授权、V2、MX、收件人窗口和 40/day 冻结约束。

English: Phase 1 delivers the full development copy, isolation, runtime map, writer/send indexes, read-only data evidence and six bilingual reports. No broad refactoring occurred. The first business implementation objective is safe lead replenishment, preserving the five frozen files, authorization, V2, MX, recipient windows and 40/day limit.

## P0 — 生产污染与重复执行 / Production corruption and duplicate execution

| 编号 / ID | 证据与风险 / Evidence and risk | 后续动作与验收 / Next action and acceptance |
|---|---|---|
| P0-1 | 多个默认 DB 路径、硬编码生产 launcher、继承 env、Wrangler remote 与原始凭据。 / Multiple DB defaults, production launchers, inherited env, cloud writes and credentials. | 运行任何业务测试前创建 OS 隔离边界，统一断言 DB 在 DEVELOPMENT_ROOT、网络默认拒绝；禁止部署注册。生产文件保持不动。 / Enforce OS isolation, development-only DB and deny-network before executable tests; no deployment registration. |
| P0-2 | `bd_db.py:923` start_job_run 可返回 False，但 orchestrator:760 不检查；`:792` 锁先读后写，非原子；release 不验证 holder。 / Job-start rejection ignored; non-atomic lock and unowned release. | 在开发修复非冻结编排/DB 协调，原子获取、owner release、明确去重键、重复触发直接退出。双进程测试只能一个执行者。 / Fix non-frozen coordination with atomic ownership and duplicate rejection; prove single winner. |
| P0-3 | job timestamp 用 SQLite UTC，而 stale cleanup 用本地 datetime.now；可能把新作业误认为已过 2h。 / UTC storage compared with local naive time can falsely expire running jobs. | 统一 job/lock UTC 时钟及显示转换，测试 UTC+8 和跨午夜；更正旧验收时间解释。 / Use consistent clocks and validate timezone/day boundaries. |
| P0-4 | frozen sender test_mode 无 test_email 时跳过授权且在 SMTP 后检查 plan；旧 sender 被 BD_TEST_MODE=true 解锁。 / Empty test recipient bypass and conditional legacy unlock. | 当前不改冻结文件。先由隔离层拒绝该配置并阻止所有传输；记录后续单独发送器安全修复项，只有范围获准后修改。 / Block configuration/transport externally now; record separately scoped frozen-sender fix for later authorization. |
| P0-5 | `sendmail:618 -> quit:619 -> DB commit:645` 之间可失败；SMTP 已接受但库未记账有重复风险，事务不涵盖网络。 / Post-acceptance quit/commit failures create ambiguous delivery. | 先补故障模拟和 unknown-delivery 对账设计；冻结期间不实施 sender 改动。不得凭“原子 DB 提交”宣称 exactly-once SMTP。 / Design reconciliation and failure tests; do not alter frozen sender or claim exactly-once SMTP from DB atomicity. |
| P0-6 | Task installer、WorkBuddy 历史 automation 与 service schedule 常量并存；同日 inventory 多跑。 / Multiple scheduling artifacts and repeated daily inventory. | 先在开发文档确定一个调度权威及唯一 job key；下一部署阶段再由授权的运行配置导出核实。当前不启停或删除任何生产任务。 / Define one authority and unique job key; verify registrations only in an authorized deployment phase. |
| P0-7 | FSP create_plan 会取消同类型所有 planned；无 pre-send 全局原子互斥；与发送并行有竞态。 / Plan replacement can race with sending. | 非冻结入口先做持锁与阶段互斥设计/测试；FSP 本身保持冻结。验收不取消被消费的计划。 / Add coordination outside frozen files; ensure in-flight plan is not replaced. |

中文：P0 不意味着先重写 SMTP。先建立开发执行隔离、去重和时间语义，再恢复上游补库；发送器发现仅记录为后续限定范围安全事项。本阶段没有改任何冻结文件。

English: P0 does not call for rewriting SMTP first. Establish development isolation, deduplication and time semantics, then repair replenishment. Sender findings remain separately scoped safety items. No frozen file changed in Phase 1.

## P1 — 自动发现、官网与邮箱补库 / Automatic discovery, website and email replenishment

1. 中文：修 BrowserMapsProvider 的参数/环境优先级，保留显式 file 模式；测试无缓存 direct 链路与可解释 provider 错误。English: Fix constructor/environment precedence while retaining explicit file mode; test uncached direct selection and provider errors.
2. 中文：新增独立官网解析任务，消费 website_lookup_required/manual_review 队列；用商户名称、电话、地址交叉验证，目录与社媒只做线索，不伪造官网。English: Add a website-resolution worker consuming unresolved review rows, matching merchant name, phone and address; directories/social pages are hints, not fabricated official sites.
3. 中文：统一官方页面 fetch/extract 结果契约，保存最终 URL、HTTP/TLS 成功、可见原文、抓取时间/哈希、身份证据；按确定性规则选邮箱。English: Standardize fetch/extract output with final URL, HTTP/TLS success, visible text, timestamp/hash, identity evidence and deterministic email selection.
4. 中文：修补 scanner 与 manual verifier 的 snippet 契约；失败提交不永久排除，以状态/next_retry_at/次数预算控制重试。English: Repair scanner-to-verifier excerpt contract and replace permanent exclusion with stateful bounded retries.
5. 中文：消除上游 A0 tri-state 对 NY 候选的提前截断：建立“已验证证据候选”状态，真正是否可发仍调用冻结 V2/MX；不得改标签骗过门禁。English: Prevent tri-state A0 promotion from prematurely discarding NY evidence candidates; retain frozen V2/MX as the actual sending decision.
6. 中文：库存同时报告 discovered/website_verified/email_evidenced/V2/MX/SAFE_FSP、unique_orgs 和 rejection reasons；用后者决定完成。保留发送上限 40，不默默把所有目标改成 40。English: Report the full funnel, unique organizations and rejection reasons; use safe plan eligibility for completion while retaining the 40-send cap and distinct inventory targets.
7. 中文：修 cursor/cache 页身份、TTL 和扫描公平性；不可让前 20 个待查行长期饿死后续行。English: Fix page/cache identity, TTL and queue fairness so old pending rows cannot starve newer candidates.

中文：P1 验收在开发 fixture 完成：至少覆盖一例无官网商户成功补齐官方证据并通过现有 V2/MX 到开发 FSP；同时覆盖无邮箱、身份不符、假邮箱、退订、已联系、网络失败，全部不可误入计划。第二次执行不能重复入库，真实 SMTP=0；真实生产导入/发送属于后续部署流程。

English: P1 acceptance uses development fixtures: at least one website-less merchant reaches verified first-party evidence and an FSP through existing V2/MX, while no-email, identity mismatch, guessed email, suppression, contacted and network-failure cases remain excluded. Reruns are idempotent and real SMTP is zero. Production ingestion/sending belongs to a later deployment workflow.

## P2 — 可靠性与测试 / Reliability and tests

中文：按 TEST_GAP_ANALYSIS 的顺序补配置契约、E2E fixture、双进程锁、90 天证据、MX 状态/新鲜缓存、时区/UTC、配额和失败注入测试。固定第三方依赖和浏览器版本；统一重试预算与清晰错误分类；报告每个阶段的独立更新时间，不用 bounce 成功覆盖 tracking/host 心跳陈旧。

English: Add configuration contracts, end-to-end fixtures, multiprocess locks, evidence-age/MX/cache/timezone/quota and failure-injection tests in TEST_GAP_ANALYSIS order. Pin dependencies/browser versions, bound retries, classify errors and report per-stage freshness instead of masking stale tracking/host state with successful bounce scans.

## P3 — 清理与可维护性 / Cleanup and maintainability

中文：在调用和调度证据充分后，逐个退役旧发送/采集入口，合并非冻结配置来源；分离可复用 scanner 与 standalone runner；移除失效注释/未使用 schedule 常量；建立 artifacts/runtime/source 边界与数据库版本清单。不删除无法证明无调用的归档，也不把清理作为补库修复的前提。

English: After proving caller/scheduler ownership, retire obsolete entrypoints individually, consolidate non-frozen configuration, separate reusable scanner from standalone runner, correct stale comments and unused schedule constants, and establish source/runtime/artifact and database-version boundaries. Do not delete unproven dependencies or make cleanup a prerequisite for replenishment repair.

## 交付与下一阶段边界 / Deliverables and next-phase boundary

中文：六份报告为 ARCHITECTURE_MAP、PRODUCTION_ENTRYPOINTS、LEGACY_COMPONENT_AUDIT、ENRICHMENT_GAP_ANALYSIS、TEST_GAP_ANALYSIS、REMEDIATION_PLAN。附带静态索引、脱敏配置键清单、快照计数、冻结哈希。下一阶段应从 P0 开发隔离/协调及 P1 最小补库修复开始；需要业务代码变更时再实施，当前停在已完成审计。

English: The six reports are ARCHITECTURE_MAP, PRODUCTION_ENTRYPOINTS, LEGACY_COMPONENT_AUDIT, ENRICHMENT_GAP_ANALYSIS, TEST_GAP_ANALYSIS and REMEDIATION_PLAN, supplemented by static indexes, redacted configuration keys, snapshot counts and frozen hashes. The next implementation phase should begin with development isolation/coordination and minimal replenishment repairs. This delivery stops at the completed audit, not broad refactoring or production deployment.
