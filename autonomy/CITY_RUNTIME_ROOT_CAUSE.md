# 城市根因调查 / City root-cause investigation

根因未确认。精确生产源码已恢复并匹配，排除源码因SAFE56立即早退；真实入口、活动州与阶段轨迹待补证。以下保留历次调查及后续更正。
Root cause unconfirmed. Exact live-matching source recovered, excluding immediate SAFE56 exit in that source. Actual entry, active state and stage traces remain required. Chronological findings and corrections follow.

# 城市运行只读调查 / Read-only city runtime investigation

## 已确认 / Confirmed

- 正式桥接源码 `C:/Users/15690/WorkBuddy/deploy-channel/bin/bridge.py` 的 AUTH_POST 只有 health/preflight/apply/status/rollback/register/releases/telemetry。没有固定生产源码导出、阶段日志、任意SQL/文件或safe-snapshot入口。不能将telemetry中提示safe-snapshot当成实际支持。
  AUTH_POST exposes only health/preflight/apply/status/rollback/register/releases/telemetry. No fixed production-source export, stage logs, arbitrary SQL/files or safe-snapshot endpoint exists. The SAFE message does not establish a callable endpoint.
- `autonomy/runtime/channel_takeover_20261021/production_snapshot`仅包含discovery_service和retail_city_queue两个快照，不含bd_orchestrator。开发bd_orchestrator SHA为 `b67a2564e66456d4b0744c40865e43c4f4dbe05fe598092394cbd75c83cdf7ff`，与用户提供的生产 `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903`不同。因此开发编排路径只能作为候选假说，不能证明生产早退。
  The existing production snapshot contains only discovery_service and retail_city_queue, not bd_orchestrator. The development orchestrator hash differs from the supplied production hash; development control flow is a hypothesis source, not proof of a production early exit.
- 正式telemetry.py `_inventory`只返回最后8条记录的started_at/business_date/status/target/actual/stop_reason/stage/run_id，没有finished_at、阶段调用或错误。其running_inventory_24h_window实际SQL为近2小时，字段名不等于查询范围。
  `_inventory` returns only eight recent summaries without finished_at, stage calls or exceptions. The field named running_inventory_24h_window actually queries two hours.
- `_automations`的active_inventory_count只数指定ID是否ACTIVE，不证明其他automation没有承担同类Inventory。全局唯一性需固定语义分类/已登记Inventory全清单证据。
  active_inventory_count checks only whether the designated ID is ACTIVE. Global uniqueness requires a fixed semantic classification or full registered Inventory inventory.
- `_city`返回completed_at为空的最近3行，含QUEUED，不是纯active列表，也不保证包含下一优先城市。
  `_city.active` contains the latest three unfinished rows, including QUEUED; it is neither a strict active list nor authoritative next-priority city evidence.
- 历史交接文件 `handoff/phases/WORKBUDDY_READONLY_ACCEPTANCE_REQUEST_20261016.md`明确当时没有可调用WorkBuddy消息入口，未确认送达。当前需另由父代理查询连接能力；不能将保存本地文件或GitHub issue等同运维接收。
  The historical handoff explicitly states no callable WorkBuddy messaging entrypoint and unconfirmed delivery. Parent must recheck available connections; a local file or issue alone is not operator receipt.

## 尚未证明的假说 / Unproven hypotheses

本地stage_inventory在target已足时仍执行城市完成检查→激活→run_places_batch→website→staging→linked→完成检查，target_met在尾部。因此仅target_met不能解释停滞。生产可能存在不同版本路径、恢复筛选、异常捕获或完成条件问题，必须从固定生产源码及实际run证据辨别。
The local inventory stage performs city completion, activation, discovery, website/staging/backlog and final completion even at target. target_met alone cannot explain the stall. Production may differ in version, filtering, exception handling or completion predicates; fixed-source and actual-run evidence are required.

## 最小固定观测登记合同 / Minimal fixed observation registration contract

1. 固定导出bd_orchestrator.py（或仅stage_inventory及其固定依赖函数的不可变快照），不接受用户任意路径。返回SHA/字节数/采样时间，与telemetry现场SHA一致。
   Export only the fixed orchestrator or immutable named functions; no client path input. Return SHA, size and time matching live telemetry.
2. 固定最近已部署后Inventory记录及该run_id允许列表；返回finished_at、automation触发关联、各阶段entered/exited/call_count/result/error_class/stop_reason及证据引用，历史无轨迹时明确NOT_RECORDED。
   Fixed post-deploy Inventory run allowlist with finish time, trigger linkage and stage entered/exited/call counts/results/error classes/evidence references. Missing historic traces must be NOT_RECORDED.
3. 固定Cooperstown与Lake Placid的城市队列/查询族聚合、completion_checks逐项布尔、pending状态计数。非终态仅不透明record reference、attempt_count/last_failure_at/next_retry_at/error_class，不含商家身份、域名或邮箱。
   Fixed-city queue/family aggregates, completion predicates and pending counts; opaque references and recovery timing/error category only, without merchant identifiers/domains/emails.
4. 固定Provider按城市/run/time窗统计，真实请求数、成功/失败、审计引用。0与UNKNOWN区分。
   Fixed Provider aggregation by city/run/window, with actual request/success/failure counts and audit references; distinguish zero and UNKNOWN.
5. 固定24h/7d资格聚合及正式只读MX正负控+SAFE计算，版本、门禁摘要、测量时间和两个独立快照用于对账；无支持入口则UNKNOWN。
   Fixed 24h/7d qualification aggregates plus official read-only MX controls and SAFE measurement, with version, gate summary, timestamps and two independently reconciled snapshots. Unsupported measurement remains UNKNOWN.

全部接口固定参数/枚举和有界输出，仅mode=ro/query_only，禁止任意SQL/路径/命令、业务写入、SMTP、改城市状态或手动Inventory。WorkBuddy实施权限边界，Codex消费合同、验证和开发故障复现。
All interfaces use fixed bounded parameters/enums and read-only/query-only access. No arbitrary SQL/path/command, business mutations, SMTP, city override or manual Inventory. WorkBuddy owns the boundary; Codex consumes, validates and reproduces.

执行结果：已完成只读能力与代码路径调查；未证明生产根因、未生产修改、未重发4A.8U、未调用数据库。风险：当前摘要型遥测容易过度解释唯一性、时间窗和城市active含义。下一步：固定观测登记及生产源码对账，随后最小复现和修复。敏感检查：无token、凭据、客户明细。
Result: read-only capability/control-flow audit complete; production root cause unproven; no production changes, 4A.8U reapply or database access. Risk: summary telemetry can overstate uniqueness, window and active-city semantics. Next: fixed observation registration and source reconciliation, then minimal reproduction/repair. Sensitive-data check: no tokens, credentials or customer records.

## Git精确源码恢复补证 / Exact Git source recovery addendum

随后扫描全部Git历史bd_orchestrator.py（5个提交），找到 `df209f529ac1925da3689ebf0bc38c8b8ada8c0d:bd_orchestrator.py` 精确SHA为 `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903`。原字节保存 `autonomy/runtime/bd_full_20261022/production_orchestrator_matched.py`，未读取生产文件。上文“缺少生产orchestrator快照”的阻塞已由Git对象恢复解除；现场遥测再次SHA匹配后，可将此源码用于生产路径分析，但不代表某次运行实际装载它。
A subsequent scan of all five Git commits touching the orchestrator recovered the exact production hash from `df209f529ac1925da3689ebf0bc38c8b8ada8c0d:bd_orchestrator.py`. Original bytes are saved in the ignored runtime copy without reading production files. This resolves source availability; after live-hash reconciliation, it supports production path analysis but does not prove that a specific run loaded the module.

恢复源码stage_inventory在SAFE足量时仍经过完整Discovery路径，target_met仅尾部finish。因此可排除“此源码本身因SAFE56立即早退”；仍需证明调度器确实执行此入口。active_discovery_state是强制限定条件，可能使Cooperstown所属NY与实际活动州不一致；当前遥测缺少此配置，属于待证假说，不是根因。
The recovered stage_inventory still executes Discovery at sufficient SAFE, with target_met only at final finish. This excludes immediate SAFE-based exit in this exact source. Scheduler-entry evidence is still needed. Mandatory active_discovery_state could select a state other than Cooperstown's NY; the current telemetry omits it, so this remains a hypothesis.

## 固定源码合成路径验证 / Fixed-source synthetic path validation

新增固定Git恢复工具 `tools/reconstruct_production_orchestrator.py`，不接受任意commit/路径输入。新增 `tests/test_production_inventory_path.py`：仅读固定Git字节，AST隔离state resolver及stage，不执行模块顶层代码，所有DB/Provider/业务副作用均Mock。
Added the fixed-Git reconstruction tool with no arbitrary commit/path input. The new test module extracts only state resolution and stage functions through AST without module-top-level execution; database, Provider and business mutations are mocks.

实测 `python -X utf8 -m unittest tests.test_production_inventory_path -v`：7/7 PASS。覆盖SAFE56仍完整调用四lane、非NY活动州只向该州传递、空/非法州终止、程序异常停止并重抛、错误summary不因达标成功、锁冲突与dry-run不采集。
Actual execution: 7/7 PASS. Covers all four lanes despite SAFE56, non-NY state propagation, empty/invalid state failure, programming-exception stop/reraise, failure summaries despite target sufficiency, lock conflicts and no-discovery dry-run.

此为源码路径排除与复现基础，不是生产根因修复验收；A_CITY_REPAIR_TESTED不能因此置true。
This supports source-path exclusion and future reproduction, not production root-cause repair acceptance; it must not set A_CITY_REPAIR_TESTED=true.


交接 / Handoff: https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/2#issuecomment-6330120094
09:28 +08无新回复，不重复申请。 / No new reply at 09:28 +08; no repeated request.
