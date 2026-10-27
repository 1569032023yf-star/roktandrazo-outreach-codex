# U1当前恢复点 / U1 current checkpoint

## 最新覆盖记录 / Latest superseding checkpoint

2026-10-27 最新断点：只读增长账本快照检查器固定 da443fde93bf41d222b93ae5dff9610a3d4b11d5，独立8项测试及限定范围审核通过；主线组合84项通过（5.518秒）。模块只接收获准导出的bytes和SHA，内存检查精确schema、完整映像及未结算状态；拒绝WAL依赖、未知状态和预算超限。见 SNAPSHOT_COMPATIBILITY_REVIEW.md。 / Latest checkpoint: read-only growth snapshot inspector pinned at da443fde93bf41d222b93ae5dff9610a3d4b11d5 passed independent8-test scoped review; combined84 tests passed in5.518 seconds. Approved exported bytes and SHA are inspected in memory for exact schema, complete image and unresolved states; WAL dependence, unknown states and exhausted budgets are rejected.

这不是迁移实现或生产导入验收。未结算预留不退款、不重放；2秒是软时限。下一自动动作：结合既有Issue2合同回复核对正式依赖与导出兼容；无回复时继续离线导入合同和业务语义校验，不能用正确SHA替代来源授权。整体 DEVELOPMENT_COMPLETE=false、RELEASE_READY=false、PRODUCTION_DEPLOYED=false、PRODUCTION_ACCEPTED=false，增长UNKNOWN。 / This is neither migration nor production import acceptance. Unresolved reservations are not refunded or replayed; the2-second deadline is soft. Next: reconcile formal dependencies/export compatibility with the existing Issue2 response, or continue offline import-contract and business-semantic validation while it is pending. A matching SHA is not source authorization. All overall development/release/production flags remain false; growth UNKNOWN.

本断点生产副作用为零，未创建Inventory、访问生产数据库、发信或修改配额。旧833项全量比较仍仅适用于b69214d，不扩展为新模块全量验收。 / No production effects, Inventory creation, production database access, mail or quota changes occurred. The earlier833-test comparison remains scoped to b69214d, not full-suite acceptance of the new module.

桥接聚合固定68802d5通过独立13项审核；最终组合76项通过（5.032秒）。实现完整签名事件窗口、跨登录生命周期与同秒歧义拒绝、无人登录证据门禁、稳定acceptance_id，重签同事实不新增验收周期。进程端点相同不声称连续存活。见BRIDGE_SESSION_REVIEW.md。 / Bridge aggregation68802d5 passed13 independent tests; the76-test combined suite passed in5.032 seconds. Signed event coverage, lifecycle and timestamp ambiguity checks, login-free gates and stable acceptance IDs are implemented. Re-signing facts does not create a new cycle; matching process endpoints do not prove continuity.

正式接口最小只读合同已通过Issue2 comment6435605069发出，本周期检查无后续回复，不重复发请求。下一工程断点为只读导入/迁移兼容准备；真实OS证据生产端、正式后端及安装权限仍待受控接入。 / The minimum read-only interface contract was requested through Issue2 comment6435605069; no subsequent reply was found and no duplicate request was sent. Next engineering checkpoint: read-only import/migration preparation. Real OS collectors, formal backend and installation permissions remain gated.

2026-10-27：此前内存阻塞已解除并实际完成全量比较。b3a0d3a基线与b69214d候选均833项，37失败17错误，ID完全相同，新增回归0（不是全绿）。详见REGRESSION_COMPLETED.md及机器JSON。旧段落关于“全量未运行”的状态仅为历史。

The earlier memory blocker was overcome and full comparison completed: baseline b3a0d3a and candidate b69214d each ran833 tests with identical37 failure/17 error IDs, zero new regressions, not all green. See REGRESSION_COMPLETED.md and its JSON. Older statements that full regression has not run are historical.

e3f3220离线单槽执行适配器已获独立13项定向审核；主线63项组合测试通过。包含指定锁身份、签名缺槽传递、未知不重放、旧回执不能清除新UNKNOWN树。详见EXECUTION_ADAPTER_RESULT.md和ADAPTER_REVIEW.md。当前继续实现跨登录/无人登录可信证据聚合；不得把离线adapter当正式后端。

Offline adapter e3f3220 passed13 independently run tests and a63-test combined suite. It binds the designated lock, preserves signed missed slots, prevents unknown replay and rejects old receipts clearing newer UNKNOWN trees. Cross-logon/login-free evidence aggregation is next. The offline adapter is not a formal production backend.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false. Issue2仍无6402130583之后的新补证，未重复回执。生产身份、出口、唯一权威切换及管理员安装均未执行。

All overall development/release/production states remain false. Issue2 has no new evidence after6402130583; no duplicate acknowledgement or identity, egress, authority cutover or administrator installation occurred.

源码候选 / Source candidate: `1eca7e7f361f48dccdd7cca7b80c1ef7cb3ae0ac`。

D五项阻断与两项边界已在c17dfca修复并通过独立复审。最新组合测试已直接使用LedgerEvidenceVerifier及签名有效期；独立22项单进程测试通过（1.153秒）。详见D_REREVIEW.md与ADAPTER_INTEGRATION_REVIEW.md。 / Five D blockers and two boundary findings were fixed at c17dfca and independently re-reviewed. The latest composition tests directly use LedgerEvidenceVerifier and signed expiry; all22 independent single-process tests passed in1.153 seconds. See the two review reports.

宿主可用内存459276KB，本周期未启动多进程或完整suite。完整基线/候选失败ID比较仍未完成，NO_NEW_REGRESSION=UNKNOWN。 / Available host memory was459276KB; no multiprocessing or full suite was launched. Complete baseline/candidate failure-ID comparison remains pending; NO_NEW_REGRESSION=UNKNOWN.

新增SOURCE_CANDIDATE_MANIFEST.json按固定Git blob记录五个候选文件SHA；生产目标均UNAPPROVED，不能作为安装清单执行。回滚遵循U1_RELEASE_GATES.md，保留未知结果与预算账本，不恢复陈旧数据库覆盖已发生副作用。 / The source manifest pins five Git-blob hashes with all production targets UNAPPROVED; it is not an executable installation manifest. Rollback preserves unknown outcomes and budget history under U1_RELEASE_GATES.md.

Issue2本周期核对最新仍6402130583，无新补证；未重复回执。canonical及投影已移除过期的认证故障阻塞，改为等待新自然运行证据。 / Issue2 still ends at6402130583 with no new evidence; no duplicate receipt was sent. Canonical queue and projection replace the obsolete authentication blocker with fresh natural-run evidence pending.

DEVELOPMENT_COMPLETE=false; SCOPED_REVIEW_PASSED=true; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.

下一自动动作：资源允许时重跑多进程与完整基线候选回归；继续正式执行适配、可信身份与唯一锁合同的受控接入准备。生产安装/身份/ACL/出口/窗口授权尚未请求，不执行生产变更。 / Next: rerun multiprocessing and complete comparable regression when resources permit; continue controlled preparation of the execution adapter, trusted identity and sole-lock contracts. Installation, identity, ACL, egress and window approval have not been requested; no production changes are performed.

本周期生产副作用为零，保留原Inventory，未采集、写生产数据库、发信或调整配额。 / This cycle had no production effects: original Inventory preserved, no collection, production database writes, mail or quota changes.

## 后续信任边界验证 / Subsequent trust-boundary validation

7f848aa补充真实签名的过期、未来时间、缺失有效期、别名注入、错误身份与来源拒绝用例；独立2项测试通过（0.049秒），见TRUST_BOUNDARY_REVIEW.md。本轮可用内存538856KB，继续不运行重型测试。源码实现未改变，原Git blob清单仍有效，发布与生产状态保持false。 / 7f848aa adds signed expiry, future timestamp, missing lifetime, alias injection and identity/source rejection cases. Two independent tests passed in0.049 seconds; see TRUST_BOUNDARY_REVIEW.md. Free memory was538856KB, so heavy testing remains deferred. Implementation bytes did not change; the prior source manifest remains valid and release/production states remain false.

## 缺槽签名合同修复 / Missed-slot signature contract fix

41a5516修复已重现的缺陷：调用方省略签名中的非空missed列表时，原实现会遗漏缺槽审计却接纳最新slot；现在在事务前拒绝不匹配，畸形元素统一返回合同错误。独立定向1项通过；主线32项单进程slot及增长组合测试通过（1.669秒）。签名适配另2项通过。已更新固定源码SHA清单。 / 41a5516 fixes a reproduced omission: the caller could omit signed missed slots while the latest slot was admitted without their audit records. Mismatches now fail before transaction, and malformed entries produce contract errors. Independent targeted test passed;32 single-process slot/growth tests passed in1.669 seconds, plus2 adapter tests. Source hashes were refreshed.

独审见SCHEDULE_CONTRACT_REVIEW.md。可用内存530512KB，完整/多进程回归未运行。RELEASE_READY=false，PRODUCTION_DEPLOYED=false，PRODUCTION_ACCEPTED=false；不宣称生产漏槽已修复。 / See SCHEDULE_CONTRACT_REVIEW.md. Free memory was530512KB; full and multiprocessing regression did not run. Release, deployment and production acceptance remain false; no claim of fixing live missed firings.
