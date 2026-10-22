# 旧重试元数据调查 / Legacy retry metadata investigation

## 19:00 正式读取纠正 / Correction from the 19:00 live read

中文：live_city_1.json 于 2026-10-22 19:00:26+08 直接从受限正式接口返回：571 的 attempts 和 failure_events 均从 1 增至 2，最近失败 18:30:11，下一次可重试 19:00:11；linked blocker 仅剩 556，565 已不在该集合。城市仍 active、四项完成条件仍 false、Lake Placid pending。旧快照描述“三条没有变化”以及“565 无法自愈”不得作为当前结论。565 为何退出集合仍无逐条终态或历史阶段证据，不能自动认定成功验证或网络耗尽。

English: live_city_1.json directly returned from the restricted production interface at 19:00:26+08 shows reference 571 progressing from one to two attempts and failure events, with last failure at 18:30:11 and next retry at 19:00:11. Only reference 556 remains a linked blocker; 565 left that set. Cooperstown remains active, four completion conditions still fail, and Lake Placid remains pending. The old snapshot cannot support unchanged-three-blockers or non-self-healing-565 claims. Why 565 left the set is not recorded as per-record terminal or historical stage evidence; do not infer verified success or network exhaustion.

中文：因此下面旧结构案例仅是通用兼容风险，不是已证当前根因；不推荐据此修改生产重试语义。优先补真实阶段记录：job_runs 已有 current_step TEXT，缺独立事件列。可以评估把 Inventory 专用 current_step 升为有版本、严格脱敏、有界的 JSON 轨迹，通过原 /v1/runtime 原样返回并由 Codex 验证。每个事件含阶段、开始/完成、时刻、序号及无身份计数；完成事件必须在工作提交后写入；异常不能伪造完成。只覆盖最后标签不能证明完整轨迹。此选项无需数据库迁移或 bridge 改动，但必须先验证外部读者、大小、截断与兼容，并独立审核。

English: The legacy cases below are generic compatibility risks, not an established current root cause; changing production retry semantics on that basis is not recommended. Prioritize actual stage recording. job_runs has current_step TEXT but no event column. Assess a versioned, strictly redacted, bounded JSON Inventory trace in that existing field, exposed unchanged through /v1/runtime and independently validated by Codex. Events contain phase, start/completion, timestamp, sequence and identity-free counts; completion follows work commit and errors never fabricate completion. Overwriting a final label does not prove full traversal. This option avoids schema migration and bridge changes, but requires validation of external readers, size, truncation and compatibility, plus independent review.

中文：本次只读分析，没有修改受跟踪文件、生产数据或运行配置。依据为本地正式对应源码、WorkBuddy 固定交接快照，以及三个纯函数合成案例。此报告不是生产阶段轨迹，也不是生产验收。

English: This read-only analysis changed no tracked file, production data or runtime configuration. It uses the locally matched production sources, the fixed WorkBuddy handoff snapshot, and three synthetic pure-function cases. This is neither a production stage trace nor production acceptance.

## 已证实 / Verified

中文：CITY_STAGE_TRACE 显示 Cooperstown 20/20 查询族完成，571 为 website_lookup_pending，556/565 为 linked backlog 阻塞引用；九项城市条件中四项不满足。active_discovery_state 为 NY。精确 orchestrator 的 stage_inventory 第 419–472 行读取该配置，依次走新发现、未链接官网解析、未链接后处理、linked backlog，再执行城市完成检查；库存达标不会提前返回。以上源码调用顺序不能证明历史 run 实际遍历了所有阶段。

English: CITY_STAGE_TRACE shows 20/20 completed query families, pending website lookup reference 571, linked-backlog blocker references 556/565, and four failing city-completion conditions. The active discovery state is NY. The matched orchestrator's stage_inventory, lines 419–472, resolves that setting and orders discovery, unlinked website resolution, unlinked postprocessing, linked backlog and a final city-completion check. Inventory sufficiency does not return early. Source order is not evidence that a historical run traversed every stage.

中文：retail_city_queue.py 第 238–253 行对 linked ledger 缺 unavailable_attempts 时直接允许重试；具有非零计数但缺完整失败历史时拒绝重试。第 256–272 行只有完整、间隔合规且计数恰为 3 的真实失败历史及相应终态标记才接受自动工作结束。第 286–334 行 linked 完成阻塞判断不检查重试历史是否可执行，所以可能同时出现“不允许重试”且“仍阻塞城市”。

English: retail_city_queue.py lines 238–253 allow linked retries when unavailable_attempts is absent, but reject nonzero counters with incomplete histories. Lines 256–272 accept automatic completion only with a complete, correctly spaced three-failure history and matching terminal markers. The linked completion blocker in lines 286–334 does not test whether the retry history is executable, so a row can remain a city blocker while being ineligible for retry.

| 合成 ledger / Synthetic ledger | due | deferred |
|---|---:|---:|
| attempts=31，缺 unavailable_attempts / absent unavailable_attempts | true | false |
| attempts=20，unavailable_attempts=1，无 failures / no failures | false | false |
| unavailable_attempts=3，只有终态文字 / terminal text only | false | false |

中文：本地 Python 纯函数实测以上三种结果。它们说明源码的兼容问题，不是对 556/565 实际字段的复现。交接 CITY_STAGE_TRACE 没有给出这两条的原始脱敏 ledger。WORKBUDDY_LONG_TERM_OPERATIONS 的总结文字称其计数 20/31、完成失败计数 1/缺失、due=True；若其中一条真实为非零计数且失败历史非法，则源码结果应为 due=False。不能忽略这个差异直接认定两条都每轮重试。

English: Local Python pure-function evaluation produced the table above. These demonstrate source compatibility behavior, not exact reproduction of references 556/565. CITY_STAGE_TRACE omits their actual redacted ledgers. The WorkBuddy operations summary reports attempts 20/31, unavailable counts one/absent, and due=True. If a row actually has a nonzero unavailable count and invalid history, the source returns due=False. That difference must be reconciled before asserting both rows retry each firing.

## 修复建议与边界 / Repair recommendation and boundaries

中文：最保守兼容修复是给内部恢复账本增加版本，首次遇到明确不兼容的旧结构时原样归档旧 ledger 和原因，初始化一个新的真实失败序列；后续只累计实际完成且相隔至少 1800 秒的失败。不得把总 attempts 转换成已证失败、补造时间或直接把旧计数设为 3。正常身份、历史、第一方官网和 SAFE 门禁必须继续运行。新格式应幂等，完整有效旧账本保留，数据库失败整次回滚，非法/未知终态不自动豁免。具体迁移条件仍需实际脱敏字段以免扩大范围。

English: The most conservative compatibility repair is a versioned internal recovery ledger: archive an explicitly incompatible legacy ledger unchanged with a reason, then begin a new evidence-backed failure sequence. Count only real completed failures spaced at least 1800 seconds apart. Never convert total attempts into proven failures, invent timestamps, or set the old counter to three. Preserve identity, history, first-party-site and SAFE gates. Migration must be idempotent, retain valid old histories, roll back on database failure, and never exempt unknown terminal markers. Exact redacted fields are still needed to constrain the migration predicate.

中文：tests/test_city_network_recovery.py 已明确要求：不完整/伪造耗尽标记不能抑制工作；内部 fetcher 错误不能消耗网络失败预算；provider_process_no_result 不能视为真实网络失败。直接“旧计数够大就转终态”会违反这些现有安全要求。若需要把不可恢复元数据转人工隔离，必须使用独立、诚实的“元数据不可证明”终态合同及测试，不能伪称 network_retry_exhausted；这比仅重建账本更大范围，尚不建议作为首选最小补丁。

English: Existing tests require incomplete/forged exhaustion markers not to suppress work, internal fetcher errors not to consume transport-failure budgets, and provider_process_no_result not to count as a real network failure. Terminalizing solely from a large legacy attempts counter violates those requirements. An explicit manual quarantine would need a separate truthful unprovable-metadata contract and tests, never a false network_retry_exhausted label; that is broader than rebuilding a ledger and is not the preferred minimal patch.

中文：571 的单次失败摘要具有到期时间，但未提供准确 error 字符串、linked 状态与最近 run 的逐条处理证据，因此只能说“可进入进一步检查”，不能保证会自然耗尽。下一步消费既有受限接口及已提交交接中更多精确字段，构造等价脱敏复现，再实施最小补丁和独立审查。

English: Reference 571 has one summarized failure and a due timestamp, but its exact error string, linkage and per-record execution in the latest run are absent. Natural exhaustion is therefore unproven. Next, consume the existing restricted interfaces and fixed handoff for exact redacted state, reproduce equivalent rows, then implement and independently review the minimal repair.

## 571 与预算检查 / Reference 571 and budget inspection

中文：源码不支持直接归因“每轮四 lane 预算挤占”：官网解析先取符合条件的全部行，过滤 network_recovery_due，再按 max(1, budget) 截取；当前 pending 总数为 1、manual retryable 为空，默认 20 或最小正预算均应容纳该唯一候选。正常后处理也只有一条 pending。linked backlog 按最早 last_attempt_at 排序，默认 20，当前仅两条 linked 阻塞，也不足证明饥饿。具体环境预算、linkage 与门禁结果缺失，预算原因仍未证实。

English: The source does not directly support budget starvation: website resolution loads all eligible rows, filters network_recovery_due, then applies max(1, budget). With one pending row and no retryable manual refs, the default budget of 20 or the minimum positive budget accommodates that candidate. Normal staging likewise has one pending row. Linked backlog prioritizes oldest last_attempt_at and defaults to 20, against only two linked blocker refs. Actual environment limits, linkage and gate outcomes are missing, so starvation remains unproven.

中文：还存在一个选择边缘差异：官网解析 SQL 使用 COALESCE(website,'')=''，而后处理使用 strip() 判断缺官网。空白字符串会被解析器排除，但后处理只返回 website_lookup_pending、不改变持久化状态。它是一个可复现通用卡住路径，不是已证生产原因。571 仍可能因 linked 严格门禁、非法完整重试历史或 resolver 的非网络程序错误未推进。摘要的失败事件“数量 1”不能证明事件时间、错误、状态及 next_retry_at 一致。

English: Another selection edge exists: resolution SQL tests COALESCE(website,'')='', while postprocessing strips whitespace. A whitespace-only website is excluded from resolution, while postprocessing merely returns website_lookup_pending without a persistent transition. This is a reproducible generic stuck path, not an established production cause. Strict linked gates, invalid full retry history, or nontransport resolver errors could also prevent reference 571 advancing. A summarized event count of one does not prove valid event timestamps, status, error and next_retry_at consistency.

自检 / Self-check: 双语 / bilingual; 无商家身份或秘密 / no merchant identity or secrets; 生产副作用 0 / zero production effects; 未完成未标完成 / no incomplete work marked complete.
