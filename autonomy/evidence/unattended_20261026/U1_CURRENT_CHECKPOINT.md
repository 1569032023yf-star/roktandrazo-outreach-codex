# U1当前恢复点 / U1 current checkpoint

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
