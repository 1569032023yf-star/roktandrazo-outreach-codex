# D 独立复审 / Independent D re-review

固定版本 / Pinned revision: `c17dfcab8189ebc0f7c3dbf0ca07d1d859ed1407`。

结论 / Verdict: **PASS_FOR_OFFLINE_D_MODULE_AND_BOUND_CLAIM_PROTOCOL**。原五项阻断与两项边界在本次范围内已修复。该结论不等于完整U1回归、生产发布或业务验收。 / The original five blockers and two boundary findings are resolved within this scope. This is not full U1 regression, production release or business acceptance.

## 逐项核验 / Findings verification

| 原问题 / Finding | 复核 / Verification |
|---|---|
| 不完整latest误计数 / Incomplete latest counted | measurements.complete持久化，整个baseline区间任一不完整观测使增长与净变化UNKNOWN，后续完整观测不抹去缺口。Persisted completeness gates the whole interval. |
| 首个无效baseline冻结 / Invalid first baseline freezes | 无历史观测隔离；仅历史完整、完整测量、双SAFE一致、非历史导入才能建立baseline。First eligible observation establishes the baseline; quarantine does not block history import. |
| SAFE时效与下界 / Freshness and lower bound | 默认300秒、配置1–3600秒；baseline<=latest<=now；旧值单列历史字段，增长/当前SAFE拒绝。Explicit bounded freshness and baseline range enforced. |
| 规则ABA / Rule ABA | 全区间扫描异规则，返回UNKNOWN。Whole-interval rule mismatch remains incomparable. |
| 预算与claim绑定 / Budget-to-claim binding | 签名两侧共同绑定inventory/slot/epoch/owner/run/request；run固定摘要；先预留再claim，claim失败保留charged，重复不重claim。Common signed identities and conservative durable sequencing verified. |
| last_merge覆盖 / Merge overwrite | 逐事件merge_events查询，后一天merge不消除前日不可比较标记。Per-event merge history preserves previous-day invalidation. |
| qualified_hash含退出者 / Exited qualification | current_qualified/current_rule与首次合格分离，摘要按当前规则当前合格集合生成。Current qualification digest is separate from first qualification history. |

## Schema与组合 / Schema and composition

Schema v2在每个事务核验user_version及表定义集合；旧库、错版本或表结构漂移失败关闭，无隐式迁移。固定格式时间错误与跨日run wall上限持久化也已检查。 / Schema v2 validates version and table definitions on every transaction; legacy or changed schemas fail closed without implicit migration. Fixed-format timestamp errors and persisted cross-day run wall limits were inspected.

实际DurableSlots组合覆盖成功claim、预算拒绝保持pending、冲突claim保留预算、run/request/slot/owner/epoch不匹配拒绝，以及claim token摘要关联。使用临时exclusive_lock上下文；它证明本地协议所需锁存在，不证明生产唯一锁路径已正确接入。 / Real DurableSlots tests cover successful claims, pending preservation on budget denial, retained reservations on claim conflict, identity mismatches and token digest linkage. A temporary exclusive_lock context proves the local protocol precondition, not correct integration with the sole production lock path.

组合测试的verify夹具真实校验合成HMAC，但使用测试映射与固定expires，未直接使用LedgerEvidenceVerifier。此前AB适配器审核独立有效；生产接入前仍须把正式签名adapter、批准锁路径与D组合纳入同一端到端验收。不得将该测试描述为生产签名证据链已验收。 / Composition tests verify synthetic HMACs but use fixture mapping and expiry rather than LedgerEvidenceVerifier directly. Prior AB adapter review remains separate; production integration must exercise the approved adapter, lock path and D protocol together. This test is not production evidence-chain acceptance.

## 独立执行 / Independently executed

独立重新运行test_growth_ledger全部单进程22项：**22 passed，1.162秒，退出码0**。明确排除test_multiprocess_budget_cap，未启动多进程或全量suite。静态核对实现、原审核与修复报告。测试仅TemporaryDirectory、合成签名和SQLite，不联网、不触碰生产数据库、不发信。 / Independently reran all 22 single-process growth tests: **22 passed in 1.162 seconds, exit 0**. The multiprocessing budget test was explicitly excluded; no full suite ran. Implementation and both review records were inspected. Tests used temporary SQLite and synthetic signatures only, with no network, production database or sending.

## 保留门禁 / Remaining gates

- 本版本多进程预算测试与基线/候选完整回归尚未完成；资源允许后再执行。 / Current-version multiprocessing and complete baseline/candidate regression remain pending memory availability.
- 生产历史导入/迁移、证据来源完整性、时效政策、唯一锁路径、正式执行入口和发布器支持仍需正式验收。签名本身不证明业务资格或完整性。 / Production history migration, source completeness, freshness policy, sole lock path, formal entry point and publisher support remain unaccepted; signatures alone do not establish qualification truth.
- 跨库不是原子事务；claim或确认写失败保持保守预留并要求对账，不自动退款/replay。 / Cross-ledger operations are not atomic; claim or acknowledgement failure requires reconciliation, without automatic refund or replay.
- **D_SCOPED_REVIEW_PASSED=true; FULL_REGRESSION_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; BUSINESS_GROWTH_VERIFIED=false.**

Reviewer未改源码、未提交、未部署。 / Reviewer changed no implementation, made no commit and performed no deployment.
