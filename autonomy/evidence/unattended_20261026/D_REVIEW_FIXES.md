# D 独审修复记录 / D Review Fixes

修复基线 / Fix baseline: 9a4b99fc34072afa4c2c74968e2e6ba8c36911ca
原审核 / Original review: D_REVIEW.md — CHANGES_REQUIRED
本记录是实现者修复自检，非独审通过 / This is an implementer repair check, not independent approval.

## 已修复与反例 / Fixes and counterexamples

1. 中文：measurements 持久化每次 complete。报告检查从冻结基线至报告时间的每条观测；任一不完整或异规则使区间增长及净变化 UNKNOWN，后续完整样本不抹去缺口。
   English: Every measurement persists completeness. Reports inspect the whole baseline-to-report interval; any incomplete or different-rule observation leaves growth/net change UNKNOWN. Later complete samples do not erase the gap.
2. 中文：无历史完整性时先隔离观测，仅记测量与回执，不生成组织或 baseline，因此不阻止历史初始化。只有历史完整、测量完整、双SAFE一致且非历史导入的观测才能首次冻结基线；先前失败测量不会占位。
   English: Observations before complete history are quarantined as measurement/receipt records without organizations or baselines, preserving history initialization. Only complete-history, complete, agreeing-SAFE, non-import measurements freeze the first baseline. Rejected first observations cannot occupy it.
3. 中文：report 默认300秒 freshness，明确参数限1至3600秒；必须 baseline.observed <= latest.observed <= now 且属该业务日。过期SAFE仅出 SAFE_HISTORICAL_VALUE 和时间戳，当前SAFE、净变化及增长UNKNOWN。生产时效策略仍须正式确认。
   English: report uses a 300-second default freshness bound with an explicit 1–3600-second parameter. The latest observation must be no earlier than the baseline, no later than now, and within the business day. Stale SAFE is historical value/timestamp only; current SAFE, delta and growth remain UNKNOWN. Production freshness policy still needs formal integration.
4. 中文：完整区间规则检查拦截 A→B→A；不能只比较两端相同规则。
   English: Whole-interval rule checks reject A→B→A instead of trusting equal endpoint rules.
5. 中文：真实 reserve_then_claim 要求 lock_recovery 实际活动锁上下文。签名预算与签名slot证据必须共同绑定 inventory/slot/epoch/owner/request_id；run_id为固定身份集合摘要，不能任意借用另一个run。预算先持久化 binding，再claim，成功后记录token摘要与slot库token关联。第二步失败不退款；回执丢失不重claim。不宣称跨库原子。
   English: The real reserve_then_claim requires an active lock_recovery context. Signed budget and slot evidence bind inventory/slot/epoch/owner/request_id; run_id is derived from that fixed identity, preventing borrowing another run. Budget binding persists before claim, then the token digest links to the slot token. Claim failure does not refund; lost acknowledgement does not replay. No cross-database atomicity is claimed.
6. 中文：逐事件 merge_events 保存合并时间，不再覆盖last_merge。历史日后再合并也不会抹掉原日不可比原因。
   English: Per-event merge timestamps replace overwritten last_merge state, preserving prior-day invalidation after later merges.
7. 中文：组织新增 current_qualified/current_rule，与不可变首次合格时间分开；冻结 qualified_hash 使用当前合格、当前规则集合。退出后重入仍不算首次资格。
   English: current_qualified/current_rule are distinct from immutable first qualification. Frozen qualified_hash represents currently qualified identities under the current rule; reentry is not first qualification.

## Schema及边界 / Schema and boundaries

中文：schema v2同时校验user_version与全部表定义；无版本旧库、错版本或表定义变化在初始化及每次事务失败关闭，不隐式迁移。新临时库测试通过。时间溢出转换为固定INVALID_TIMESTAMP/INVALID_DAY，不泄露输入。每日业务日期仍以Asia/Shanghai 01:00分界。每个run的wall cap首次持久化，跨日不得借新日更高上限扩大原run。

English: Schema v2 checks user_version and all table definitions on initialization and each transaction; unversioned legacy, wrong-version or changed schemas fail closed without implicit migration. Fresh temporary databases pass. Time overflow becomes fixed INVALID_TIMESTAMP/INVALID_DAY without input echo. Business days retain the Asia/Shanghai 01:00 boundary. Each run persists its original wall cap, preventing a larger next-day cap from expanding an existing run.

中文：当前存储仅支持新隔离schema；真实历史导入/迁移、生产证据和时效政策、正式执行入口及发布器新增文件支持均未验收。合并后受影响日仍保守UNKNOWN，需要新可比较基线。签名证明来源，不替代源端完整性与资格真实性。不会重开采集或发送。

English: Current storage supports fresh isolated schemas only. Real history migration, production evidence/freshness policy, formal execution integration and publisher support for new files remain unaccepted. Merge-affected days conservatively remain UNKNOWN pending a new comparable baseline. Signatures establish source authenticity, not source completeness or eligibility truth. No collection or sending is enabled.

## 测试 / Testing

中文：单进程定向22项通过，1.156秒。包含五阻断的实际反例、不同日期合并、当前资格摘要、schema篡改、datetime溢出、真DurableSlots成功组合、预算拒绝保持pending、冲突claim保留预算、签名run/request不匹配。宿主内存限制下明确排除现存多进程预算测试，未跑全量；不能将上一版本并发通过当作本次新版本并发验收。

English: 22 selected single-process tests passed in 1.156 seconds, covering all five blocking counterexamples, cross-day merges, current qualification digests, schema tampering, datetime overflow, real DurableSlots composition, budget denial preserving pending state, conflicting claims retaining budget and signed run/request mismatches. The existing multiprocessing budget test was explicitly excluded under memory constraints; no full suite ran. Prior-version concurrency results are not claimed as current-version concurrency acceptance.

中文：只改D专属源码/测试/报告，全部临时SQLite，无生产数据库、SMTP或网络调用。独审PENDING，RELEASE_READY=false，PRODUCTION_DEPLOYED=false。下一步固定SHA交独立Reviewer复审，资源允许后重跑双进程预算。报告双语/数量/风险/秘密/未执行事项自检通过。

English: Only D-owned source, tests and reports changed; all databases are temporary, with no production DB, SMTP or network calls. Independent review is PENDING, RELEASE_READY=false and PRODUCTION_DEPLOYED=false. Next pin the SHA for independent re-review and rerun two-process budget testing when resources permit. Bilingual/count/risk/secret/unperformed-work checks passed.
