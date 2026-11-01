# U1审计目录绑定与新证据消费 / Audit-directory binding and evidence consumption

实际开始2026-11-02T01:46:51.5953037+08:00，触发2026-11-01T17:46:43.253Z。恢复本地/远端HEAD182d4f28c4f7f347a103bec5565f063ff537c8f5；本轮源码832f2198e384ccba12828350181415a1049f6f22。原未跟踪文件和宿主工作树保留，持久recovery guard未删除；未发现其他U1进程。只创建本轮开发锁，结束释放。平台无会话级硬时限接口，未新增系统任务，命令有界并在45分钟内保存。

Actual start and trigger are separate above. Recovery HEAD verified locally/remotely; source pinned above. Existing untracked work/host worktree/recovery guard preserved. No competing U1 worker observed. Own cycle lock released at close. No session hard-limit API; bounded commands, no system task, finish within45 minutes.

## 实现与验证 / Implementation and validation

新增显式Windows离线入口exercise_bound_audit_contract_offline，持有审计目录及祖先无DELETE共享句柄，贯穿条件复核、journal写入/关闭、最终状态读回。3项实际Windows测试覆盖每步effect/readback中目录rename拒绝、PUBLISH效果后异常保留pending、相同operation不重放、退出释放、非显式offline与失败条件无副作用。20定向/115组合全部通过，分别1.365s/9.518s。源码清单见SOURCE_MANIFEST.json。

New explicit Windows offline wrapper holds audit directory/ancestor identities through condition checks, journal closure and final status read. Three real Windows tests cover rename denial at each effect/readback, pending PUBLISH after effect failure, same-operation no replay, release and fail-closed scope.20 targeted/115 combined pass. Directory identity does not protect journal child content by ACL; no formal lease/trusted adapter/install authority. Independent review PENDING; old scoped review does not cover this pin. No833 full-suite inheritance or all-green claim.

## WorkBuddy固定证据 / Pinned evidence

WorkBuddy 13d061a82568bc147efa689742a61b3e06d95a31已读取8文件（7份当前投影+历史Phase0）。8/8 Git blob原字节重算、JSON及声明version/envelope核验；没有外部正式JSONSchema。3份内嵌payload摘要不匹配（scheduler/runtime/SAFE），3份匹配（city/provider/releases）；operations与Phase0未声明payload。operations缺producer；来源为sources端点，未补造。原字节保存在source，逐文件来源/采样/摘要见VERIFICATION.json。

Eight pinned files actually read; all Git blobs and declared envelopes verify, not external schema conformance. Three embedded digests mismatch existing metadata-stripping/sorted-JSON recipe; retain as reservations, no tampering inference. Missing producer/hash preserved. Historical Phase0 is not the latest production state.

| 文件 / File | Git blob SHA |
| --- | --- |
| CITY_STAGE_TRACE.json | 55e4670e9871be6a9b92ab19f628be709ec8e864 |
| INVENTORY_SCHEDULER_RECONCILIATION.json | e6cb99392d3889040c3c3c447fa8c900b79a6b5d |
| PRODUCTION_RUNTIME_LATEST.json | dd069d4a8747729213b7634a19210e869c52950a |
| PROVIDER_REQUEST_AUDIT_24H.json | 1098b00a669a572c7dc524b390fee03adf34d6da |
| RELEASE_REGISTRY_SNAPSHOT.json | 6f5b0c91208891e7835964caa378d4121d3b8a5b |
| SAFE_AUTHORITY_SNAPSHOT.json | a8e7467eccdfd4f5d668ef8378abf6347e1ca4eb |
| WORKBUDDY_LONG_TERM_OPERATIONS.json | bb175b03d8834b5b2b8026ec1fdaa37ccacff7b1 |
| PHASE0_STATE_REFRESH_20261029.json | ce2a755875ce6bc707bc20dcc155911d535a108a |

SAFE68/68，采样11/1 22:47:40与22:53:05，measured22:41:14。旧69到68算术差-1，但两测量相距82666s非86400s；自报24h-1/7d+12且reason/unavailable仍否定同规则baseline。严格24h/7d与BUSINESS_GROWTH=UNKNOWN，不将算术差当业务增长。

SAFE68 agrees twice. Old69 to68 differs by-1 over82666 seconds, not strict24h; seven-day baseline unavailable. Producer growth claims conflict with missing-comparable-baseline text. Strict growth remains UNKNOWN.

Inventory7 firing仅5真实completed且一对一authority/时间窗口通过；2无run不能推定原因。新增92b9d406、493f7e5c、f2830908均target60/actual69及16个阶段事件，晚于run的SAFE68不是同一采样。drift744.59s与674.95s超过600s，零漏跑UNKNOWN。下一计划11/1 23:56:42.790+08在本轮消费时已过去，后续结果未提供。running_inventory_now=6与completed列表冲突保留；唯一WorkBuddy Inventory可见，但系统任务不可枚举，global uniqueness UNKNOWN。

Seven firings, five exact verified production rows; two nonexecutions unresolved. Three new real runs and16 events each verified; historical run count69 differs in time from SAFE68. Excess drift and missing runs prevent zero-miss acceptance. Next planned timestamp is historical at consumption; no outcome invented. Preserve running-count contradiction and system-task visibility gap.

Cooperstown正式关闭9/9；Lake20/20但places_matrix_completed_web_pending、5/9检查、completed_at=null；Ithaca未提供，旧冲突未解。operations仍称Cooperstown不会关闭，标旧文案冲突，不重做patch。Provider全城市city_id=null，7d42 rows/42 requests/42 success/0fail/0timeout一致；city22 24h0行、查询20/20；Lake累计56属于不同口径。

Cooperstown closed; Lake matrix complete but web/completion pending; Ithaca unprovided. Stale operations closure text retained. Provider current aggregates reconcile within their scopes, not runtime/live acceptance.

8791 UP_SESSION_SCOPED仅历史session健康，bootfalse、登录注册未观察；跨调用/登录/无人登录持久性未通过。7877非交互出口UNKNOWN。SMTP自报raw0、来源一致、today0/historical517、未授权邮件/写入0；Codex本轮生产数据库/SMTP访问0，未采集、部署、服务/ACL/代理修改或重复apply。生产DB跨日hash不同不能声称全局未变。

Session health is not unattended persistence.7877 noninteractive egress UNKNOWN. Producer mail/write safety observations retained; this cycle performed no production actions and claims no global DB immutability. No release reapply.

最新生成11/1 22:53:22，Git22:53:30（+8s）；采样、生成、提交分开。历史Phase0仍10/29 11:55，旧5a290610提交11:52倒置不修改，历史Codex HEAD不当当前HEAD。最新commit不是旧报告的生成时钟。

Latest generation precedes commit by8 seconds; sample clocks remain distinct. Historical Phase0/old11:55 versus11:52 discrepancy is preserved verbatim, never silently repaired or treated as latest state.

## 恢复与发布 / Recovery and publication

沿用Issue2；本轮先读全comments，最新旧回执6546897497只消费30334633，未发现13d061a回执。新回执发布并独立回读前CODEX_HANDOFF_CONSUMED=false。发布后另存CONSUMPTION_RECEIPT.json，不改原producer证据。canonical本地autonomy/runtime/queue.json，Git投影autonomy/AUTONOMOUS_TASK_QUEUE.json，checkpoint unattended_20261026/U1_CURRENT_CHECKPOINT.md。

Existing Issue2 only; no duplicate backend request/channel. Consumption becomes true only after new receipt publication and exact independent readback. Source evidence remains immutable. Local canonical and Git projection/checkpoint updated separately.

下一离线项：审计子日志对象替换/内容完整性与跨进程退出故障合同、固定源码独审；正式lease/ACL/可信Windows adapter、成功持源发布仍阻塞。版本化取消费用与reserve-before-intent既有实现保留，不重复实现。发布清单仅本轮源码/测试/证据/状态；备份恢复基线182d4f2及原状态，离线回滚使用reviewed revert，不恢复/重放UNKNOWN效果，无生产回滚授权。

Next: audit child-journal identity/content and process-exit fault contracts, pinned independent review. Formal lease/ACL/trusted adapter and successful held-source publication remain blocked. Existing versioned cancellation/reserve-before-intent implementation preserved. Release scope is offline files only; recovery baseline182d4f2, reviewed revert if needed, no UNKNOWN effect replay or production rollback authority.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.

正式消费完成 / Formal consumption completed: Issue2 comment6561646296 independently read back exactly. CODEX_HANDOFF_CONSUMED=true. See CONSUMPTION_RECEIPT.json; prepublication false in VERIFICATION.json remains historical. 本轮结束前保留原恢复guard，仅释放所属cycle锁。
