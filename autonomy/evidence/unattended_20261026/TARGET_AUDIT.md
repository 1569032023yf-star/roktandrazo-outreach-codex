# Inventory 目标只读审计 / Read-only Inventory Target Audit

日期 / Date: 2026-10-26 (Asia/Taipei)
源码检查时HEAD / HEAD during inspection: c735b0593f9f02f9a6dfb71edc42414f050e6756

## 当前代码事实 / Current code facts

中文：outreach_control.py:26-36 的工作日库存目标由 SAFE_INVENTORY_TARGET 控制，默认 NEW_OUTREACH_TARGET(40)+10=50，且最低40；inventory_target_for_date（83行）周末返回 max(60, INVENTORY_TARGET)。这是库存充足目标，不是每日新增组织目标，更不是发送授权。本轮没有修改配置或配额。

English: outreach_control.py:26-36 derives the weekday inventory target from SAFE_INVENTORY_TARGET, defaulting to NEW_OUTREACH_TARGET(40)+10=50 with a floor of40. inventory_target_for_date at line83 returns max(60, INVENTORY_TARGET) on weekends. This measures inventory sufficiency, not daily new organizations or sending authorization. No configuration or quota changed.

中文：本仓 bd_orchestrator.stage_inventory（394-484）没有 safe>=target 提前返回。先读取库存，再运行原城市队列的发现、官网、后处理和linked backlog，最后才把库存gap=0标为target_met。Provider错误即使SAFE达标也停止并记录失败。run_places_batch最多3页；正常官网与后处理仅max(1,配置)未见硬20上限，linked backlog则min(20,两个配置)；页预算不等于请求/浏览器导航/美元预算。

English: Repository bd_orchestrator.stage_inventory at lines394-484 has no early return for safe>=target. It reads inventory, executes discovery, website, postprocessing and linked-backlog lanes in the original city queue, and only then records target_met for zero inventory gap. Provider errors stop the run even when inventory is sufficient. Discovery is capped at three pages; normal website and postprocessing limits use max(1,configured) without a hard20 cap, whereas linked backlog uses min(20,both configured limits). Page limits are not request, navigation or monetary budgets.

中文：已有 tests/test_phase4a8r_continuous_discovery.py 覆盖SAFE49/50/51与目标50、SAFE59/60与目标60，均仍执行发现；覆盖页上限、错误、锁和dry-run。tests/test_production_inventory_path.py 从固定 df209f529ac1925da3689ebf0bc38c8b8ada8c0d 字节重建AST（源码hash e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903），已有SAFE56仍依序四条lane的隔离测试。这是历史固定字节测试，不证明当前生产调用路径。本审计只读测试，没有重跑或采集。

English: Existing tests/test_phase4a8r_continuous_discovery.py checks SAFE49/50/51 against target50 and SAFE59/60 against target60, all still executing discovery, plus page caps, errors, locks and dry-run. tests/test_production_inventory_path.py reconstructs fixed df209f529ac1925da3689ebf0bc38c8b8ada8c0d AST bytes, hash e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903, with a SAFE56 four-lane test. This is historical pinned-byte testing, not proof of the current production invocation. This audit read tests without rerunning them or collecting data.

中文：检索未找到可证明当前外层调度/计划因target_met短路的受控源码；本仓.workbuddy目录不存在。必须取得实际计划判定/执行器入口及同一run审计，不能从target_met终态推断短路。父级给出的6ba549fc交接（工作日50/周末60、SAFE56、Lake4/20、3次firing恢复）作为待父级来源核验的外部事实引用；该对象不在本仓Git，未独立重取。无需据此重新认证，亦不采纳LocalSystem建议。

English: Searches found no controlled source proving the current outer scheduler/planner short-circuits on target_met; this repository has no .workbuddy directory. Obtain actual planner decisions, executor entrypoint and same-run audit; a terminal target_met cannot establish short-circuiting. Parent-provided6ba549fc handoff facts (weekday50/weekend60, SAFE56, Lake4/20, three recovered firings) remain externally sourced facts for the parent's verification; that object is absent from this repository and was not independently retrieved. They do not require reauthentication, and the LocalSystem suggestion is not adopted.

## 每日冻结与增量合同建议 / Proposed daily freeze and incremental contract

中文：采用现有业务日边界，明确记录Asia/Shanghai（当前与用户Asia/Taipei同UTC+8，不改变业务日规则）。首个获准测量事务冻结 baseline_id、日期、资格规则hash、DB快照标识、已知组织集合及合格集合hash/数量；迟到首测标记partial_day，不能回填成午夜基线。当天重启复用同baseline，规则变化另立版本且不直接相减。

English: Use the existing business-day boundary, explicitly recording Asia/Shanghai (currently UTC+8 like user-facing Asia/Taipei) without changing its rule. The first approved measurement transaction freezes baseline_id, date, eligibility-rule hashes, DB snapshot identity and known/qualified organization-set hashes/counts. A late first measurement is partial_day, not a fabricated midnight baseline. Restarts reuse the baseline; rule changes create a separate version that is not directly subtracted.

中文：建立全历史 first-qualified ledger，以canonical organization_key唯一约束，记录首次发现/首次完整资格通过时间、规则版本和脱敏证据引用。NEW_UNIQUE_ORGANIZATIONS 是当日首次确认身份且历史未见的组织；NEW_QUALIFIED_NEW_ORGANIZATIONS 是其中当日首次全部资格通过者；EXISTING_ORGANIZATIONS_NEWLY_QUALIFIED 单列既有候选新转化。重复抓取、退出后重入SAFE、历史导入、身份合并不能再次计新客户。rule-evaluation成功但发送冻结不改变资格计数；不生成发送授权。

English: Maintain an all-history first-qualified ledger uniquely keyed by canonical organization_key, recording first discovery/full qualification times, rule version and redacted evidence references. NEW_UNIQUE_ORGANIZATIONS counts newly identity-confirmed, historically unseen organizations; NEW_QUALIFIED_NEW_ORGANIZATIONS counts those first passing all eligibility gates that day; EXISTING_ORGANIZATIONS_NEWLY_QUALIFIED separately counts conversion of known candidates. Repeated scraping, SAFE re-entry, historical imports and identity merges must not recount new customers. Frozen sending does not change verified qualification counts or create sending authority.

中文：SAFE_NET_CHANGE单独分解新增资格、既有转化、资格移除/过期、去重合并、规则变动与无法归因残差。SAFE总数从56到56也可能新入2/移出2；56到57也可能只恢复旧客户。双读不一致或基线不完整时当前SAFE/净增保留UNKNOWN，新增客户账本有独立完整证据才单独出数。

English: Decompose SAFE_NET_CHANGE separately into new qualification, existing conversion, removal/expiry, deduplication merges, rule changes and unexplained residual.56 to56 may conceal two entries and two exits;56 to57 may merely restore an old customer. Disagreeing readings or incomplete baselines leave current SAFE/net change UNKNOWN; report independent new-customer ledger counts only when their evidence is complete.

## 成本上限方案 / Cost-cap proposal

中文：保持唯一原Inventory及既有每次最多3页，不创建追赶循环或第二collector。提出日级硬上限（具体数值待既有预算授权证据，不擅自提高）：Provider操作次数、HTTP/导航次数、官网页数、浏览器分钟、付费整数微单位、每次wall-clock。按run/slot/request幂等键，在同一互斥事务先reserved再派发；unknown outcome占用reserved直至对账，超限DEFER到下一合法slot，重启/网络恢复不重置日账。缓存命中不应当作网络请求；request_count=1和cost_units=0不证明实际单请求或零成本。预算足够仅是必要条件，来源429/验证/禁限仍停止，不绕过。

English: Preserve the sole Inventory and existing maximum three pages per invocation, with no catch-up loop or second collector. Propose daily hard caps for Provider operations, HTTP/navigation requests, website pages, browser minutes, integer paid micro-units and per-run wall-clock; values require existing budget authority and must not be raised implicitly. Reserve under the same exclusive transaction before dispatch using run/slot/request idempotency keys. Unknown outcomes retain reservations until reconciliation; exhausted budgets defer to the next legitimate slot. Restarts/network recovery do not reset the daily ledger. Cache hits are not network requests; request_count=1 and cost_units=0 do not prove one actual request or zero cost. Budget availability is necessary but never overrides429, verification or source restrictions.

中文：测试建议：日切与迟到baseline、重启重复事件、组织别名合并、资格退出再进入、同日规则变化、SAFE双读冲突、未知请求占额、并发预留超限、缓存与导航分项成本。工程方案先纯离线验证，再按正式发布门禁；本报告未生产部署、采集、写数据库或改变配额。敏感信息与双语自检通过。

English: Proposed tests cover day rollover/late baseline, restart replay, organization aliases/merges, qualification exit/re-entry, intraday rule changes, disagreeing SAFE readings, unknown reserved requests, concurrent over-reservation and cache/navigation cost separation. Validate offline before formal release gates. This report deployed nothing, collected nothing, wrote no database and changed no quota. Bilingual and sensitive-information checks passed.
