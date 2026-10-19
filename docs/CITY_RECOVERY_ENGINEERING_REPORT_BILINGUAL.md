# 城市超时恢复工程报告 / City Timeout Recovery Engineering Report

日期 / Date: 2026-10-20（Asia/Taipei）

## 目标与基线 / Objective and baseline

中文：解决已完成查询矩阵的城市仍因官网网络超时重复待处理而无法安全收尾的问题。工作树为 `roktandrazo-outreach-autonomy-city`，分支为 `codex/autonomy-city-recovery`，开发基线为 `93a8d0a25dabf509fa82cac924dd85741f17b860`。仅修改城市完成判断及官网处理模块；不重新开发、不覆盖已经上线的 SAFE50 早退修复。

English: Resolve city completion being indefinitely blocked by repeated official-site network timeouts after the query matrix is exhausted. The worktree is `roktandrazo-outreach-autonomy-city`, branch `codex/autonomy-city-recovery`, based on `93a8d0a25dabf509fa82cac924dd85741f17b860`. Only city completion and official-site processing are changed. The already deployed SAFE50 early-exit fix is neither redeveloped nor overwritten.

## 实现结果 / Implementation results

中文：缺官网解析只累计已完成、明确返回 `network_retry` 或 `network_error` 的结果。第三次失败后在已有 staging 人工复核状态记录操作终态和时间；保留原始 Provider 字段、网络 rejection、关联 lead 和证据。解析结果及计数在同一 SAVEPOINT 中更新，数据库异常全部回滚，不能消耗网络重试预算。

English: Missing-website resolution counts only completed outcomes explicitly returning `network_retry` or `network_error`. After the third failure, the existing staging manual-review state records an operational terminal marker and timestamp. Original provider fields, network rejection, lead linkage, and evidence remain. Resolution state and retry counters share one SAVEPOINT, so database failures roll back without consuming the network retry budget.

中文：已有官网的关联积压使用单独 `unavailable_attempts` 计数。只有扫描完成、未取得可用第一方页面、发生明确传输或 HTTP 不可达失败且无内部抓取异常，才累计一次；第三次交接人工复核。原有静态加浏览器访问限制终态保持原逻辑。程序异常、数据库异常、待验证/待历史检查/待提取证据均不能被当作已完成网络失败。

English: Linked backlog entries with an existing official website use a separate `unavailable_attempts` counter. One attempt is counted only after a completed scan obtains no usable first-party page, encounters an explicit transport or HTTP availability failure, and has no internal fetch error. The third failure hands the record to manual review. Existing static-plus-browser access-limit handling is preserved. Processing exceptions, database errors, and pending validation, history checks, or evidence extraction cannot count as completed network failures.

中文：城市完成门禁使用持久化操作终态排除已经交接的自动重试记录，因此原始网络 rejection 可以保留而不会永久阻塞城市；不改变查询完成、网页目录原因、断点、页面预算、去重或任何 SAFE/发送资格标准。第三次正常恢复成功时仍走原身份、历史、邮箱证据和卫生门禁，不交接人工复核。

English: City completion recognizes durable operational handoffs, allowing the original network rejection to remain without permanently blocking the city. Query exhaustion, directory reasons, checkpoints, page budgets, deduplication, SAFE eligibility, and sending gates remain unchanged. A successful third attempt follows the existing identity, history, email evidence, and hygiene gates instead of being deferred.

## 验证与审查 / Validation and review

中文：新增 14 项恢复测试覆盖 Cooperstown 完成矩阵后第三次失败才能安全收尾并激活 Lake Placid、原查询断点完全保留、重启后不重选、旧 rejection 不再永久阻塞、前两次仍重试、第三次成功正常提取、队首人工复核不饿死后续候选、内部异常不累计、数据库触发器失败回滚、畸形总尝试次数不能替代有效失败计数。新增测试全部通过。既有城市/官网/积压初轮回归 63 通过，含 34 个子测试。扩展最终回归结果见后附验证字段。

English: Fourteen new recovery tests cover Cooperstown completing its full matrix, safely closing only after its third failed attempt, activating Lake Placid, preserving every query checkpoint, avoiding reselection after restart, retaining old network rejections without permanent blockage, retrying the first two failures, normal enrichment on a successful third attempt, avoiding starvation behind a deferred row, not counting internal exceptions, rolling back database trigger failures, and rejecting malformed total-attempt counters as a substitute for completed failed scans. All new tests pass. The initial existing city/website/backlog regression passed 63 tests and 34 subtests. Expanded final regression results appear in the validation fields below.

中文：父代理执行独立审查；已根据其两项意见增加按类型核对有效计数以及直接解析入口的原子事务与失败测试。开发者自检不能替代独立审查最终结论。

English: The parent agent performs independent review. Its first two findings were addressed by validating the correct counter for each retry type and making direct resolution persistence atomic with dedicated failure tests. Developer self-review does not substitute for the independent review's final conclusion.

## 业务数量及未执行事项 / Business counts and non-executed work

| 项目 / Metric | 状态 / Status |
|---|---|
| 本轮新增测试 / New tests | 14 passed |
| 真实新增独立组织 / Real new independent organizations | UNKNOWN |
| 真实新增第一方邮箱 / Real new first-party emails | UNKNOWN |
| SAFE 总数和净增长 / SAFE total and net growth | UNKNOWN |
| Cooperstown 生产收尾 / Cooperstown production completion | NOT_VERIFIED |
| Lake Placid 生产激活 / Lake Placid production activation | NOT_VERIFIED |
| 生产部署 / Production deployment | NOT_PERFORMED |
| 生产数据库访问或修改 / Production database access or mutation | NOT_PERFORMED |
| 发邮件 / Emails sent by this workstream | 0 |

中文：城市推进证据来自隔离的临时 SQLite 测试，不能宣称生产城市已切换；没有现场生产数据，新增指标不得写成零或沿用历史 SAFE 数值。未运行真实发现、SMTP 或任何发送入口，未创建第二个 Inventory。

English: City advancement evidence comes from isolated temporary SQLite tests and does not establish production advancement. Without live production data, new-business metrics must not be reported as zero or copied from historical SAFE values. No live discovery, SMTP, or sending entry point was run, and no second Inventory was created.

## 发布清单、风险与下一步 / Release checklist, risks, and next steps

中文：发布范围严格为 `discovery/discovery_service.py` 与 `retail_city_queue.py`。新测试和本报告仅作为审核证据。`patches/autonomy_city_recovery.patch` 包含精确源码差异，`patches/autonomy_city_recovery_manifest.json` 提供开发基线及开发候选前后 SHA-256。生产前置 SHA 明确为 UNKNOWN，必须通过已有受控通道重新取得并与补丁逐项兼容；不能把开发 Git blob 校验值冒充真实生产文件校验值。基线的 `bd_orchestrator.py` 仍有历史 SAFE 早退；本次绝不部署它。

English: The release scope is strictly `discovery/discovery_service.py` and `retail_city_queue.py`. New tests and this report are review evidence only. `patches/autonomy_city_recovery.patch` contains the exact source differences, and `patches/autonomy_city_recovery_manifest.json` records development baseline and candidate SHA-256 values. Production pre-deployment hashes are explicitly UNKNOWN and must be obtained through the controlled channel and checked for exact compatibility. Development Git blob hashes must not be presented as actual production-file hashes. The baseline's `bd_orchestrator.py` still contains the historical SAFE early exit and must never be deployed in this release.

中文：下一步为独立审查最终通过、登记全新固定范围 release_id（不可复用旧 SAFE50 ID），经正式入口核实 Inventory 互斥、实时文件校验、窗口、备份完整性、原子替换及回滚。正常 Inventory 运行后观察保留记录进入人工复核、Cooperstown 收尾及 Lake Placid 下一次自动激活，并记录真实 Provider 请求、组织和邮箱增量。发布失败或指纹不匹配必须停止；回滚通过同一授权通道恢复经验证备份。

English: Next obtain final independent review, register a new fixed-scope release ID without reusing the old SAFE50 ID, and verify Inventory exclusion, live hashes, deployment window, backup integrity, atomic replacement, and rollback through the official entry point. Observe normal Inventory runs for preserved manual-review records, Cooperstown completion, and automatic Lake Placid activation on the next run, recording real provider requests and organization/email gains. Stop on failed gates or hash mismatches; use the same authorized channel to restore a verified backup if rollback is required.

中文：风险是三次持续网络不可达之后，当前城市可以结束而这些组织仍待人工核实；这是一种透明的操作交接，不是判定没有商务邮箱。没有降低 V1/V2/MX/历史/退订/抑制或发送门禁，也没有扩大生产权限。

English: After three persistent availability failures, the city can close while those organizations remain awaiting human verification. This is a transparent operational handoff, not a finding that no business email exists. V1, V2, MX, history, unsubscribe, suppression, and sending gates are unchanged, and production permissions are not expanded.

## 敏感信息与报告自检 / Sensitive information and report self-check

中文：未读取或复制任何真实凭据、生产数据库或客户邮箱。测试环境仅建立不含凭据的本地 `.env` 注释文件（Git 忽略）；报告及发布包不含令牌、SMTP 密码或客户秘密。报告已核对中英双语、执行结果、未执行事项、数量、风险、下一步和未完成状态的准确表达。

English: No real credentials, production database, or customer mailbox were read or copied. The test environment uses a local credential-free comment-only `.env` file excluded from Git. The report and release package contain no tokens, SMTP passwords, or customer secrets. The report was checked for bilingual content, results, non-executed work, counts, risks, next steps, and accurate incomplete-status labels.

## 集成兼容说明 / Integration compatibility note

中文：父代理独立审查接受最终方案，等待最终提交及回归结果。整合目标如使用较新的 5A 基线 `0ce0b10`，必须保留它既有的 `identity_review` 解析终态分支；本发布包基于 `93a8d0a` 的差异不能覆盖较新的身份门禁。受控发布前需针对实际整合版本再次确认兼容性。

English: The parent agent independently accepted the final approach, pending the final commit and regression results. When integrating into the newer 5A baseline `0ce0b10`, preserve its existing `identity_review` terminal resolution branch. This package's differences against `93a8d0a` must not overwrite the newer identity gate. Confirm compatibility again against the actual integrated version before controlled release.

## 最终验证字段 / Final validation fields

中文：最终源码扩展定向回归共 97 项通过、43 个子测试通过，用时 196.37 秒；最新 14 项恢复测试另行全部通过，用时 22.28 秒。语法检查、差异格式检查、源码和精确补丁 SHA-256 复核均通过。未执行完整全仓库回归；这里不宣称全仓库测试全绿。

English: Final-source expanded targeted regression passed 97 tests and 43 subtests in 196.37 seconds. The latest 14 recovery tests also passed separately in 22.28 seconds. Syntax checks, diff-format checks, and source/exact-patch SHA-256 verification passed. The complete repository suite was not run, and no repository-wide green claim is made.

```text
PHASE = AUTONOMY_CITY_RECOVERY
DEVELOPMENT_COMPLETED = true
TARGETED_TESTS_PASSED = 97
SUBTESTS_PASSED = 43
NEW_RECOVERY_TESTS_PASSED = 14
INDEPENDENT_REVIEW = PARENT_ACCEPTED_APPROACH_PENDING_FINAL_INTEGRATION
PRODUCTION_DEPLOYED = false
PRODUCTION_VALIDATION_PASSED = NOT_VERIFIED
ROLLBACK_AVAILABLE = REQUIRES_CONTROLLED_CHANNEL_VERIFIED_BACKUP
NEW_ORGANIZATIONS = UNKNOWN
NEW_FIRST_PARTY_EMAILS = UNKNOWN
SAFE_UNIQUE_ORGS = UNKNOWN
SMTP_ENABLED = NOT_INSPECTED
EMAILS_SENT_BY_THIS_WORKSTREAM = 0
BLOCKERS = NEW_RELEASE_REGISTRATION_AND_LIVE_COMPATIBILITY_GATES
NEXT_ACTION = INTEGRATE_PRESERVING_NEWER_IDENTITY_GATES_AND_CONTROLLED_RELEASE
```
