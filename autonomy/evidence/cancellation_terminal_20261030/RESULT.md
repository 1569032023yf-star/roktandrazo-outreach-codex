# 离线取消终态回执验证 / Offline cancellation terminal-receipt verification

固定源码 / Pinned source: `7d0858ac16b5c258761ed562fd4b6ce007165927`.
基线 / Baseline: `b3bf5660a49329af4597c4f799992f154a73e24f`.

中文：本轮实际开始2026-10-30 08:59:15+08，主树干净，无既有Python任务或runtime锁。本地canonical实际读取，初始本地/远端b3bf566一致（首次只读远端查询发生schannel断开，重试成功）。恢复AGENTS、工程责任制、规范、checkpoint及上一轮结算报告；独立主机工作树仍4d394cb，未改动。仅检查代理变量名称。原缺点号附件路径不存在，正确.codex路径可读。Issue2最新仍6493117461，没有新合同或重复申请/消费回执。

English: Actual start2026-10-30 08:59:15+08; clean primary checkout, no existing Python worker/runtime lock. Read local canonical and verified matching initial local/remoteb3bf566 (first read-only remote query hit a schannel disconnect; retry succeeded). Restored AGENTS, engineering charter/rules, checkpoint and prior settlement report; separate host worktree remains4d394cb, untouched. Proxy variable names only. Original attachment path lacks a dot; corrected .codex path readable. Issue2 still ends at6493117461, without new contracts or duplicate requests/consumption receipts.

中文：新增纯只读inspect_cancellation_terminal，定义本地候选rokt.offline-cancel-terminal.v1；这是离线提议合同，未声称正式backend已实现。调用方必须另行提供从持久记录确定的完整费用binding，不得将回执自身当成可信expected。精确校验字段集合、类型、版本、Inventory、slot/epoch/owner、原request、claim、旧lock/process摘要、各账本及backend身份、确定性取消identity和费用request。独立验证三份签名：版本化取消终态、原执行drained终态、精确费用known回执；cancelled/already_failed对应failed，already_completed对应completed，ACK/未知费用/错终态不能通过。费用向量校验复用实际GrowthLedger合同。

English: Added pure read-only inspect_cancellation_terminal and the local candidate rokt.offline-cancel-terminal.v1 contract, without asserting a formal backend implementation. Callers must separately establish the complete cost binding from persistent records, never trust a receipt as expected context. Validates exact context keys/types/versions, Inventory, slot/epoch/owner, original request/claim, old lock/process hashes, ledger/backend identities and deterministic cancellation/cost request identities. Independently verifies three signed envelopes: versioned cancellation terminal, original drained terminal and precisely bound known cost receipt. cancelled/already_failed join failed, already_completed joins completed; ACK/unknown fees/wrong terminal cannot match. Cost-vector validation reuses the actual GrowthLedger contract.

中文：2项测试含多组正反例，使用真实适配器/SQLite预留产生的完整binding及合成可信签名。三种终态正例，以及缺失、错版本、ACK、非drained、未终态、布尔epoch、错原request、过期、坏签名、未知/原执行费用回执、错claim与布尔费用均拒绝。验证前后预算、slot、journal和锁文件字节不变，预算row不变，backend仅原fixture调用1次。组合154项通过28.419秒。早期测试构造重复inventory字段及str路径错误已修正；随后发现backend_id在既有合同为受限opaque字符串而非SHA，按实际合同校正后通过。

English: Two tests with multiple positive/negative cases use full bindings produced by the real adapter/SQLite reservation and synthetic trusted signatures. Cover all three valid terminal outcomes and rejection of missing envelopes, wrong versions, ACK, undrained/unconfirmed state, boolean epoch, wrong original request, expiry, invalid signature, unknown/original-operation fee receipt, wrong claim and boolean cost vector. Budget/slot/journal/lock bytes and reservation rows remain unchanged, with one original synthetic backend call. Selected154-test combination passed in28.419s. Early fixture duplicate-inventory/string-path mistakes were corrected; backend_id was then aligned with the existing bounded opaque-string contract rather than incorrectly assuming a SHA.

中文：MATCH仅表示三份输入与指定上下文相互匹配；不读当前持久状态、不证明生产来源/采样原子性、不结算、不改journal、不解锁、不调用backend。allow_reconcile/allow_lock_recovery/allow_dispatch/allow_cancel_dispatch/production_accepted始终false；未加入旧9b28eb9/922a696生产清单。独立审核PENDING，自检不能替代独审。下一项将该候选与当前持久journal/费用状态只读关联，覆盖冲突/迟到终态；必须先维持恢复和结算权限关闭。

English: MATCH joins supplied evidence to the specified context only; it does not read current persistence, prove production provenance/atomic capture, settle money, change a journal, unlock or call a backend. All reconciliation/recovery/dispatch/cancellation/production-acceptance flags remain false; existing9b28eb9/922a696 production manifests remain unchanged. Independent review PENDING, not substituted by self-inspection. Next join this candidate read-only with current persistent journal/cost state and cover conflicting/late terminals, retaining closed recovery/settlement authority.

中文：历史WorkBuddy5a290610消费记录保留，无新生产采样或业务增长结论。8791/无人登录持久性、7877非交互出口、正式backend及宿主依赖/身份ACL仍阻塞生产验收。无生产DB、SMTP、采集、服务、调度或部署操作。平台未暴露整轮45分钟硬限时入口；全量测试各子进程900秒timeout，串行执行。新固定源码比较另见REGRESSION_COMPARISON.json，结果未完成前不沿用旧833项结果。

English: Preserve historical WorkBuddy5a290610 consumption without fresh production sampling/growth claims.8791/unattended persistence,7877 non-interactive egress and formal backend/host dependency/identity/ACL contracts still block acceptance. No production DB, SMTP, collection, service, scheduler or deployment operation. No platform-wide45-minute hard-limit control was exposed; serial full-suite subprocesses have900s timeouts. Fresh pinned-source comparison is recorded in REGRESSION_COMPARISON.json; no inherited833-test result before completion.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN

组合测试 / Selected combination:
```powershell
$env:PYTHONUTF8='1'
python -B -m unittest test_cancellation_terminal test_cancellation_settlement test_cancellation_cost test_cancellation_cost_process test_cancellation_owner_death test_single_slot_adapter test_growth_ledger test_durable_slots test_host_remediation test_host_preparation test_growth_snapshot test_growth_history_contract test_owner_drain_preflight test_drain_bundle_preflight test_release_contract autonomy.test_lock_recovery -q
```

中文：SOURCE_MANIFEST.json记录6份固定Git blob/SHA256，最小导入闭包-I隔离核验通过。Git保留基线和候选作为离线源码恢复点；需要撤回时可审查revert本候选源码提交。本轮没有生产备份、迁移或生产回滚动作；该候选未形成可发布生产包，正式发布仍须独审、获批依赖、现场备份与回滚门禁。

English: SOURCE_MANIFEST.json pins six Git blobs/SHA256 values; minimal import closure passed isolated -I verification. Git retains baseline/candidate as offline source recovery points; a reviewed revert can withdraw this candidate's source commit. No production backup, migration or rollback occurred. This candidate is not a deployable production package; formal release still requires independent review, approved dependencies and live backup/rollback gates.


Fresh pinned regression / 新固定候选全量比较：baseline b3bf5660a49329af4597c4f799992f154a73e24f versus candidate7d0858ac16b5c258761ed562fd4b6ce007165927, each833 tests, identical37 failures/17 errors by ID; NO_NEW_REGRESSION=true, not all green / 无新增回归，非全绿。See BASELINE_REGRESSION.json, CANDIDATE_REGRESSION.json, REGRESSION_COMPARISON.json.
