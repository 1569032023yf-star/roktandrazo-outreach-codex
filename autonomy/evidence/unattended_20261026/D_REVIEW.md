# D 独立审核 / Independent D review

- 固定提交 / Reviewed commit: `9a4b99fc34072afa4c2c74968e2e6ba8c36911ca`。
- 范围 / Scope: `autonomy/growth_ledger.py`, `test_growth_ledger.py`。
- 结论 / Verdict: **CHANGES_REQUIRED; REVIEW_PASSED=false; RELEASE_READY=false**。
- 资源限制 / Resource limit: 可用内存低于 1GB，仅静态审计及单进程临时 SQLite 夹具复现；未运行全量或多进程套件。Memory below 1GB; static review and single-process temporary SQLite reproductions only. No full or multiprocessing suite.

## 阻断问题 / Blocking findings

1. **P1，108、189、218–230行：不完整最新观测被标为可比较增长。** measurements 未保存 complete；report 只检查 baseline.complete。完整 baseline 后输入 complete=False 且含一个新组织，实际输出 NEW_UNIQUE_ORGANIZATIONS=1、reason=COMPARABLE，而 SAFE 为 UNKNOWN。必须持久化每次观测完整性并在所有增长门禁使用；部分观测事件不得被下一次观测自动追认为完整区间。 / Latest incomplete observation is counted as comparable growth because completeness is not persisted. Reproduction returned one new organization and COMPARABLE from an explicitly incomplete observation. Persist observation completeness and gate the complete measurement interval.

2. **P1，188行：首次不合格观测永久占用日 baseline。** complete=False 首测随后完整测量，实际增长持续 UNKNOWN；INSERT OR IGNORE 不允许首个合格测量成为 baseline。如果历史导入也尚未完成，baseline 还会阻断之后 import_history 的初始化。仅合格、历史完整且规则已确定的观测能创建固定 baseline；不合格观测另存，不覆盖已合格 baseline。 / An incomplete first observation permanently occupies the daily baseline. Later complete observations cannot recover it. Create immutable baselines only from qualifying observations; retain rejected observations separately.

3. **P1，219–223行：SAFE 无时效门禁。** 同日六小时前测量在 report(now+21600) 仍输出 SAFE_LATEST=2、SAFE_NET_CHANGE=0、COMPARABLE。需要明确最大年龄及测量区间；过期结果只能作为带时间戳历史值，不得作为当前 SAFE 或当前净增长。另 SAFE_NET_CHANGE 缺 latest.observed >= baseline.observed（218行有此条件但222行未复用），对历史 now 查询可减去未来 baseline。 / SAFE has no freshness bound: a six-hour-old same-day value is reported as current and comparable. Require explicit freshness and baseline <= measurement <= now; retain stale values only as historical observations.

4. **P2，218、222行：规则 A→B→A 的中间变化被遗漏。** 实际输入该序列后返回 SAFE_NET_CHANGE=1、COMPARABLE，仅比较区间端点规则无法证明整个区间可比。必须持久化区间规则变更，或基于相同规则重算完整两个集合并提供明确证明后才比较。 / Rule A→B→A returns comparable delta because only endpoint rules are checked. Track interval changes or require an explicitly evidenced full same-rule recomputation before comparison.

5. **P1（生产组合门禁），296–305行：预算与 slot claim 未绑定。** reserve_then_claim 的 signed budget run_id 与 slot/epoch/owner 无关联检查；可以用 run A 的批准预算申请 claim B，破坏单 run 上限归属。此方法当前不派发，故不是已发生生产越额。生产接入前需签名共同 operation/slot/run/epoch 标识，持久化两侧关联并拒绝不一致；补真实 SlotLedger 组合测试，Fake.claim 成功/失败不足。 / The signed budget run identifier is not bound to slot, epoch or owner. A reservation for run A can prepare claim B, undermining per-run attribution. This is an offline integration gate, not evidence of live overspend. Bind a common signed identity across both ledgers and test with the real SlotLedger.

## 其他边界 / Additional boundaries

- 仅保存 last_merge 会覆盖历史 merge 证据；后一天再合并后回查前一天可能失去原来的不可比较标记。应保存逐事件合并记录并按报告区间查询。 / A single last_merge overwrites historical invalidation; persist merge events per interval.
- qualified_hash 使用所有曾 qualified_at 非空的记录，并非当前合格集合；若合同要求当前合格集合摘要，需保存当前资格状态与规则。 / qualified_hash represents ever-qualified records, not the currently qualified set; align its contract and state model.
- 正向边界：BEGIN IMMEDIATE、持久化 charged、unknown 不退款、重复 request 不 replay、429 hold 持久化方向正确；此静态结论不替代跨进程完整回归。 / Positive boundaries: immediate transactions, durable charged budget, conservative unknown handling, no duplicate replay, and durable 429 hold are appropriate; static inspection does not replace complete concurrency regression.

## 复现证据 / Reproduction evidence

独立单进程使用 test_growth_ledger 的合成签名与 TemporaryDirectory，未联网、未读写生产库、未发信。 / Independent single-process reproductions used synthetic signed fixtures and temporary databases; no network, production database or SMTP.

| Case | Actual result |
|---|---|
| complete baseline -> incomplete latest with new org | NEW_UNIQUE=1; reason=COMPARABLE; SAFE=UNKNOWN |
| incomplete first -> complete latest | NEW_UNIQUE=UNKNOWN; reason=HISTORY_OR_RULE_INCOMPARABLE |
| same-day observation age 21600 seconds | SAFE_LATEST=2; SAFE_NET_CHANGE=0; reason=COMPARABLE |
| rule A -> B -> A | SAFE_NET_CHANGE=1; reason=COMPARABLE |

以上四项实际复现退出码0；13项现有测试通过为主代理提供的结果，本 reviewer 未重新运行完整测试文件。缺失的反例不能被现有通过结果覆盖。 / The four reproductions exited 0. The existing 13-test pass was reported by the parent; this reviewer did not rerun the entire file. Existing green tests do not cover these counterexamples.

开发修复后需固定新 SHA 并独立复审；生产部署、真实无人登录执行与业务增长仍未验收。 / Fixes require a new pinned SHA and independent re-review. Production deployment, no-login execution and business growth remain unaccepted.
