# 取消费用独立结算故障合同 / Independent cancellation-cost settlement failure contracts

固定测试提交 / Pinned test commit: `69c3d574552da674c343816687b79164bd34479d`.
Git blob: `57e79c3f0a431415dc03830d8066fe2b7f689e05` (`test_cancellation_settlement.py`).
SHA-256 of Git content: `098add0691d0bb8094d9e0c0b5d9d60d28c6706db7b125242039a9034bdd9d53`.
恢复基线 / Recovery baseline: `31315f84124c13a09f4091991fcdaf09ba727e3d`.

中文：本轮触发2026-10-30 07:04:41+08，实际开始07:04:49+08。核实主分支本地与远端31315f8一致、工作树干净、无既存U1 Python任务或runtime锁；读取本地canonical、checkpoint和适用工程规范。CURRENT_STATUS.md和FILE_MANIFEST.md不存在，未执行任何live操作。用户所列缺点号附件路径不存在，正确.codex附件可读。仅检查代理变量名称，不输出值或修改。Issue2仍以6493117461为最新，无新正式合同，不重复请求或生产证据消费回执。

English: Trigger07:04:41+08, actual start07:04:49+08. Verified matching local/remote31315f8, a clean main checkout and no existing U1 Python worker/runtime lock; read local canonical, checkpoint and applicable engineering rules. CURRENT_STATUS.md and FILE_MANIFEST.md are absent; no live operation was performed. The originally supplied attachment path lacks a dot; the corrected .codex attachment is readable. Inspected proxy variable names only, without values or mutation. Issue2 still ends at6493117461; no new formal contract, duplicate request or production-consumption receipt.

中文：新增4项实际SQLite集成测试，覆盖版本化取消费用结算的提交前失败/提交后确认丢失、重新打开真实账本后幂等恢复；UNKNOWN费用回执保持全额收费，原执行完成不能退款，必须另有精确绑定的known费用回执；错run/claim/原request/费用版本/取消identity/布尔epoch或未外部确认拒绝且预算及journal不变；费用已经结算加上cancel_ack仍不能替代external_drained终态，slot保留UNKNOWN直到正式原执行回执。所有journal字节保持不变，后端仅原fixture执行1次，无重放。没有实现取消终态新协议，也没有将journal标为已取消，下一项仍需版本化独立取消终态只读验证及故障合同。

English: Added four real SQLite integration tests for cancellation-cost settlement before-commit failure/after-commit acknowledgement loss and idempotent recovery after reopening the real ledger; UNKNOWN fee receipts retain the full charge and completion of the original operation cannot refund it without a separately bound known cost receipt; wrong run/claim/original request/cost version/cancel identity/boolean epoch or absent external reconciliation rejects without budget/journal mutation; a settled fee plus cancel_ack cannot replace an external_drained terminal receipt, leaving the slot UNKNOWN until the original execution receipt arrives. Journal bytes remain unchanged, with exactly one original synthetic backend call and no replay. No new cancellation terminal protocol or journal terminal transition was implemented; versioned independent cancellation terminal-receipt read-only verification/failure contracts remain next.

中文：定向4项通过，1.055秒。首轮151项组合有1项已有锁测试因Windows默认GBK读取UTF-8 fixture失败（UnicodeDecodeError），不是取消结算断言失败；随后使用仅当前测试进程PYTHONUTF8=1统一父/子进程编码复测，最终结果见下段。最初故障测试误期待OSError，按现有存储API的STORAGE_OUTCOME_UNVERIFIED修正测试后通过，未修改运行源码。测试覆盖不等于独审或生产验收。

English: Four targeted tests passed in1.055s. Initial151-test combination had one existing lock test fail when Windows default GBK decoded its UTF-8 fixture (UnicodeDecodeError), rather than a cancellation assertion. Retried with process-local PYTHONUTF8=1 for consistent parent/child encoding; final outcome follows below. The initial fault test expected OSError and was corrected to the existing storage API's STORAGE_OUTCOME_UNVERIFIED; runtime source was unchanged. Testing is neither independent review nor production acceptance.

组合命令 / Combined command:
```powershell
$env:PYTHONUTF8='1'
python -B -m unittest test_cancellation_settlement test_cancellation_cost test_cancellation_cost_process test_cancellation_owner_death test_single_slot_adapter test_growth_ledger test_durable_slots test_host_remediation test_host_preparation test_growth_snapshot test_growth_history_contract test_owner_drain_preflight test_drain_bundle_preflight test_release_contract autonomy.test_lock_recovery -q
```

中文：本轮只改测试和恢复资料，运行模块与9b28eb9/922a696生产清单均未变，未机械重跑833项旧源码全量比较，也不把旧37失败17错误提升成全绿。独立审核仍PENDING，未获得新独审。生产证据消费保持原5a290610/既有回执，无新采样；桥接8791、跨调用/跨登录持久性及7877非交互出口仍未验收。没有生产数据库、SMTP、采集、配置、部署、服务或调度操作。平台未暴露整轮45分钟硬限时入口；本轮约数分钟，未领取额外重型工作线。

English: Only tests and recovery records changed; runtime modules and9b28eb9/922a696 production manifests are unchanged. No mechanical repeat of the unchanged833-test source comparison or upgrade of its37 failures/17 errors to all-green. Independent review remains PENDING. Preserve5a290610 production evidence and its prior receipt, without new sampling;8791/cross-call/logged-off persistence and7877 non-interactive egress remain unaccepted. No production database, SMTP, collection, configuration, deployment, service or scheduler operation. No platform-wide45-minute hard-limit control was exposed; this cycle took minutes without another heavy workstream.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN

中文：最终UTF-8组合151项全部通过，26.069秒；仅覆盖上列命令选择的测试集合，不能与上一轮不同组合的151项机械视作相同覆盖。测试提交已固定69c3d57，独立审核PENDING。

English: Final UTF-8 combination passed151 tests in26.069s, limited to the modules explicitly selected above; it is not identical coverage merely because the prior different combination also counted151. Test commit pinned69c3d57; independent review PENDING.
