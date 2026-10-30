# U1恢复状态只读接入 / U1 read-only recovery-status integration

固定源码 / Source: `079792aa848aba979e2c0680eee73ec91b7f0b3a`。分支 / Branch: `codex/autonomous-bd-supervisor`。

## 本轮实际推进 / Actual progress

新增`autonomy/recovery_status.py`，把已有取消恢复日志转为路径无关、内存内的固定快照状态合同。调用者提供快照字节、独立预期SHA256和取消身份；校验独立回滚模式、完整页、schema/version、integrity、固定binding形状及时间/VM预算。只在内存SQLite读取，不打开生产或任何外部数据库路径，不读取handoffs中的旧锁资料，不回显binding或异常详情。哈希一致仅证明字节一致，来源授权仍UNKNOWN。 / Added a path-free in-memory status contract for the existing cancellation-recovery journal. Caller supplies bytes, an independent expected digest and cancellation identity. It checks standalone rollback mode, complete pages, schema/version, integrity, binding shape and time/VM bounds. Only in-memory SQLite is used; no external database paths or handoff lock details are read and no binding/exception details are returned. Digest equality proves byte identity only; source authority remains UNKNOWN.

明确区分PREPARED、COMPLETED、NOT_RECORDED和拒绝后的UNKNOWN。COMPLETED只表示恢复日志阶段，不能证明原任务终态、原锁关闭、生产验收或可再次执行；allow_dispatch/allow_cancel_dispatch/allow_reconcile/replay_allowed/production_accepted恒false。 / PREPARED, COMPLETED, NOT_RECORDED and rejected UNKNOWN remain distinct. COMPLETED describes the journal only, not execution terminal state, lock closure, production acceptance or permission to run again. All execution/replay/acceptance flags remain false.

本轮启动前已有未提交`host_readonly_http.py`与对应测试，原样保留，未纳入本轮提交或宣称已接入宿主。新模块为后续只读状态接口提供可验证数据层；尚未连接8791、SCM或生产backend。 / Pre-existing uncommitted HTTP candidate files/tests are preserved and excluded from this delivery. The module prepares a verifiable data layer, not integration into8791, SCM or a production backend.

## 实测与独审 / Tests and review

`python -X utf8 -B -m unittest test_recovery_status test_cancellation_recovery test_growth_snapshot -q`：23项通过，6.636秒；其中新增7项。真实流程先保留PREPARED故障，再完成持久恢复，读取前后数据库字节一致，后端只调用1次。覆盖缺记录、哈希错误、WAL/截断/追加字节、未知schema、深层/超长/非TEXT binding、脱敏及存在/缺记录两分支超时。 /23 tests passed in6.636s, including seven new tests. The real flow persists PREPARED on injected failure and then completes recovery. Reads preserve database bytes and the backend is called once. Coverage includes absence, wrong hashes, WAL/truncation/trailing bytes, unknown schemas, deep/oversized/non-TEXT bindings, redaction and timeouts for both present/absent records.

独审指出解析递归及NOT_RECORDED分支时间门禁，两项均已修复并加入负例。最终独审结论以本目录`INDEPENDENT_REVIEW.md`为准，不继承旧整体PASS。10份递归本地源码按固定Git字节隔离导入通过，见`SOURCE_MANIFEST.json`。 / Review identified recursive parsing and missing absence-branch deadlines; both are fixed with negative tests. The final independent verdict is recorded separately rather than inherited. Ten recursive source dependencies passed pinned-byte isolated imports.

旧833可比回归只覆盖d7d424c，本轮不重复运行或扩大该结论；`NO_NEW_REGRESSION=NOT_RUN_FOR_THIS_PIN`。生产安装、运行、身份/ACL/代理修改、数据库写入、邮件、第二Inventory均0。 / The previous833-test comparison remains scoped to d7d424c. It was neither rerun nor extended: NO_NEW_REGRESSION=NOT_RUN_FOR_THIS_PIN. Production installation/execution, identity/ACL/proxy changes, DB writes, mail and duplicate Inventories: zero.

## 外部核验及下一步 / External checks and next step

WorkBuddy main重新核对仍`13572ee9f65a71d5006b4d5f53d699bb603c4702`，Issue2最新仍6513015427，无新生产回复；未重复请求或回执。 / Fresh WorkBuddy main remains13572ee9 and Issue2 still ends at6513015427; no new production response and no duplicate request/receipt.

继续在隔离环境完成只读HTTP合同与状态层关联，核清已有未提交候选的归属及可复用性，再固定整体宿主候选独审。真实8791、生产backend、有效ACL、非交互出口及发布器依赖仍需正式证据；整体DEVELOPMENT_COMPLETE/RELEASE_READY/PRODUCTION_DEPLOYED/PRODUCTION_ACCEPTED仍false，业务增长UNKNOWN。 / Continue isolated HTTP/status integration after reconciling ownership/reuse of the pre-existing candidate, then pin and review the whole host candidate. Production interfaces, backend, effective ACLs, egress and publisher/runtime dependencies still require formal evidence. Overall development/release/deployment/acceptance remain false; growth UNKNOWN.

报告自检：中英双语，真实测试/限制/未执行/下一步明确，无凭据、Token、客户资料或代理地址。原Inventory1784775229336保留，SMTP关闭。本轮为用户触发工程，不计完整无人值守周期，operation_id=NOT_STARTED。 / Self-check: bilingual, explicit tests/limits/non-actions/next step and no secrets, tokens, customer data or proxy addresses. Original Inventory preserved; SMTP off. User-triggered engineering is not an unattended cycle; no production operation started.
