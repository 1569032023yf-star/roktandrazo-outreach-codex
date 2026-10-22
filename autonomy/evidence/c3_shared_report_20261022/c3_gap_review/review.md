# C3 独立缺口审核 / Independent C3 gap review

结论：存在可安全推进的实际工程缺口，不需要制造新业务任务或重复81项测试。当前证据不支持完整C3通过。
Verdict: Real engineering gaps can safely be addressed without inventing business activity or repeating the 81-test suite. Current evidence does not establish complete C3 acceptance.

## 事实 / Findings

1. supervisor.py:406 的 two_unattended_cycles 永远返回False，仅test_supervisor调用。它是刻意拒绝自报source的安全占位器，尚未接入权威心跳证据验证；不是所有验收状态的唯一计算入口。历史HEARTBEAT_EVIDENCE.json的true仅属旧本地任务范围，不能套用当前修复后C3。
   two_unattended_cycles always returns False and is only called by its test. This is a fail-closed placeholder rejecting self-reported sources, not an implemented trusted-heartbeat verifier or the sole acceptance-state computation. The historical true flag covers earlier local tasks, not post-repair C3.

2. 当前queue的A/B/C三个未完成条目都是app_heartbeat角色，状态awaiting_external_evidence或awaiting_heartbeat。cycle只领取queued；task_prompt不登记这些ID/角色，直接改queued将触发UNREGISTERED_TASK并隔离为unknown。原生心跳可读这些本地检查点推进授权工作，但仓内没有通用原生任务dispatch/证据接入实现。不得为让CLI活跃而改状态或扩大白名单到任意指令。
   The three unfinished queue entries use app_heartbeat roles and awaiting states. cycle selects only queued entries, and task_prompt does not register their IDs/roles. Simply queuing them causes UNREGISTERED_TASK and unknown quarantine. Native heartbeats may continue authorized work from durable state, but the repository has no generic native-task dispatch/evidence integration. Do not force activity by relabeling states or accepting arbitrary queue instructions.

3. 可复现局部缺陷：observer和CLI均调用无锁dashboard，日报read-modify-write会丢失并发历史；observer的WORKSTREAM_STATUS read-modify-write及latest观测写入也未串行。两个observer可倒序覆盖较新观测。临时目录确定性插入并发历史写入后，dashboard丢失该行，见race_reproduction.json。这证明竞态存在，未证明生产已发生数据损失。
   Reproducible local defect: observer and CLI both call unlocked dashboard; its read-modify-write can lose concurrent history. Observer workstream and latest-observation writes are also unserialized, permitting overlapping observations to publish out of order. An isolated deterministic interleaving loses a history append (race_reproduction.json). This proves a race, not an observed production data-loss incident.

## 最小下一任务 / Minimal next task

优先修共享本地报告更新：使用同一明确的报告互斥协议覆盖所有程序写者，HTTP调用留在锁外；observer将latest、WORKSTREAM的production_observation更新及dashboard更新在一致的受控段执行，dashboard CLI也遵循同协议，避免嵌套非重入死锁。日报使用临时文件、flush/fsync及replace保留原内容。检查观测generated_at，拒绝迟到旧回执覆盖较新当前段。不能把report锁恢复退化为按时间删除；可复用已验证exclusive，但必须明确与cycle持锁调用的重入关系。直接人工写同文件仍需遵循同一协议。
First fix shared local report publication: use one explicit serialization protocol for every programmatic writer, keep HTTP outside it, and publish latest observation, workstream observation and dashboard within a controlled section. The CLI must follow the same protocol without non-reentrant nested deadlock. Write the report atomically using temporary-file flush/fsync/replace. Reject older generated_at observations overwriting newer ones. Do not recover locks by age; reuse verified locking only with an explicit calling/reentrancy contract. Manual writers must also cooperate.

必要测试限定为：确定性交错不丢历史/其他workstream字段；两个观测逆序时较新者保留；CLI与observer串行且无嵌套死锁；写入/replace失败保留旧文件及原错误、锁不误放行。不必重复无关81项。
Required tests: deterministic interleavings preserve history and other workstream fields; reverse completion order preserves the newer observation; CLI/observer serialization has no nested deadlock; write/replace failures preserve prior content and primary failure without unsafe lock release. Repeating unrelated 81 tests is unnecessary.

随后可做纯只读C3证据验证器：输入外部已认证的App触发事实、持久队列租约、固定提交/源码hash、真实测试及独立review成果、授权发布与验收回写证据；输出分项VERIFIED/UNKNOWN和缺口列表，默认拒绝。用合成fixture测试逻辑仅证明验证器工程正确，绝不增加真实周期数。原生心跳固定登记此开发任务和后续独立review，禁止自动将审查结果升级生产验收。
Then implement a read-only C3 evidence verifier accepting externally authenticated app triggers, durable leases, fixed commits/hashes, actual tests and independent review artifacts, authorized deployment and acceptance writebacks. Emit per-stage VERIFIED/UNKNOWN and explicit gaps, default-deny. Synthetic fixtures validate logic only and add zero real cycles. Register a fixed native-heartbeat engineering task and independent review without promoting review into production acceptance.

## 所缺权威证据 / Missing authoritative evidence

- 多个真实App触发ID及实际开始/结束对应关系，重复/迟延/人工恢复排除；不能只信队列source标签。当前两次摘要/报告周期明确qualifies=false。
- 不同周期的任务领取、实际开发变更、测试、独立Reviewer身份与结果、下一任务选择及外部阻塞转板块证据；开发者needs_review和Reviewer completed不自动证明审核通过及成果对应关系。
- 需要发布的任务：既有正式服务的注册/预检/apply/status、operation_id与SHA一致、自然业务验收回写；不需要发布的本地任务只能验收本地子链，不可捏造发布或整体C3。
- 由WorkBuddy运维身份提供的跨会话与开机服务事实，不能以登录自启或本地进程测试替代。

- Multiple genuine app trigger IDs bound to actual start/finish, excluding duplicates, delays and manual recovery; queue source labels alone are insufficient. The current summary/report cycles explicitly qualify as false.
- Task claims, actual development, tests, independent reviewer identity/results, next-task selection and blocked-stream fallback across distinct cycles. needs_review/developer and completed/reviewer states alone do not prove approval of the matching artifact.
- For tasks requiring deployment: existing-service register/preflight/apply/status, matching operation/SHA and natural acceptance writeback. Local-only tasks establish local subchains, never invented deployment or overall C3.
- WorkBuddy operations evidence for cross-session and boot-service persistence; login startup and local process tests do not substitute.

本次仅只读源码/脱敏队列及附件，并在临时目录复现；未改源码/队列/正式报告，未触生产、凭据或SMTP，未发网络请求。审核37fdbe7、356393a；其改动是持久报告和回执，未补上述源码能力。
This review read source, sanitized queue and attachments, and reproduced a race in a temporary directory. No source, queue or shared reports were changed; no production, credentials, SMTP or network was accessed. Commits 37fdbe7 and 356393a persist reports/receipts and do not implement the missing source capability.
