# 单槽适配器独立审核 / Independent single-slot adapter review

结论 / Verdict: **PASS_FOR_OFFLINE_SINGLE_SLOT_COMPOSITION_ONLY**。

最终固定提交 / Final pinned commit: `e3f3220318be0ae8d9368229aac432438913c5f4`。提交后核对两文件工作区哈希未变化，匹配下列审查字节。 / Post-commit verification confirms both file hashes remain unchanged and match the reviewed bytes below.

审核时HEAD为b69214dcbe86a7c77a167dbf665649fa0fda08f5，适配器及其测试为未提交文件。固定工作区SHA256：autonomy/single_slot_adapter.py = 1b3740ee4ad1d15e678ab22af117b56d9b06d48a5d501bd213869fde8d9476be；test_single_slot_adapter.py = 33666c90e2bcb01bc9a719e0cffe4a9baa660450f949686f6b735b02e5073b95。后续提交应核对这些字节，不能将结论用于不同内容。

HEAD was b69214dcbe86a7c77a167dbf665649fa0fda08f5; the two adapter files were uncommitted. The workspace SHA256 values above pin the reviewed content. A subsequent commit must verify these bytes rather than inheriting this conclusion for changed content.

## 核验与修复 / Verification and fixes

- 旧适配器未传递签名missed列表，会拒绝合法缺槽计划。现已传递，测试证明缺槽持久化为deferred、最新slot单次执行。 / The initial adapter omitted signed missed slots, rejecting valid gap schedules. Forwarding is fixed; tests preserve deferred gaps while executing the latest slot once.
- 同一lease内旧完成回执可能清除另一新UNKNOWN执行的tree标记。当前修复在终态对账后检查其他claimed/running/unknown，存在则拒绝清树。独立实际两slot场景确认OTHER_EXECUTION_UNRESOLVED，锁保持unverified且清理失败关闭；新增回归测试通过。 / An old receipt could otherwise clear a newer unknown execution under the same lease. The fix rejects tree clearance while any unresolved slot remains. An independent two-slot scenario confirmed the rejection and retained unverified lock; the added regression passes.
- 锁检查绑定指定runtime路径、目录身份、现有lease内容、PID/进程身份及token；使用既有recovery guard。缺省未配置backend拒绝，scope必须isolated_offline，production_execution必须false。 / Lock checks bind the configured runtime, directory identity, existing lease, process identity and token under the existing recovery guard. Missing backend denies execution; only isolated_offline and production_execution=false are accepted.
- 预算先预留再claim/start；外部调用最多一次。错误或迟到结果保留UNKNOWN及预算，不自动退款、不重放；双签名回执绑定run/request/token及持久预留。 / Budget reservation precedes claim/start and at most one backend call. Errors or late results retain unknown state and charges without refund or replay; signed receipts bind operation identity and persisted reservation.

## 独立执行 / Independent execution

最终13项test_single_slot_adapter测试独立通过，1.798秒。测试全部使用临时SQLite、合成签名、fake backend，不联网、不采集、不触碰生产数据库、不发信。未改变实现，未提交。测试夹具已使用真实LedgerEvidenceVerifier。

All13 final adapter tests independently passed in1.798 seconds using temporary SQLite, synthetic signatures and a fake backend. No network, collection, production database or email was involved. The reviewer changed no implementation and made no commit. Fixtures use the actual LedgerEvidenceVerifier.

## 完整回归证据核对 / Full regression evidence verification

独立读取主树autonomy/runtime/u1-regression-candidate-final/result.json及基线树autonomy/runtime/u1-regression-baseline-final/result.json。两份JSON内容完全一致：833测试、37失败、17错误；失败/错误ID集合一致。两文件SHA256均88314932528b2554e30abd0a0750d4e6ada2ede8781a059d0503d39d9d1668af，与REGRESSION_FINAL_COMPARISON.json一致。该结论仅覆盖候选b69214d和基线b3a0d3a，未重跑，不继承给新适配器；不是全绿。

Both original result files were independently read. Their entire JSON content matches:833 tests,37 failures and17 errors, with identical failure/error IDs. Both hashes match the comparison report. This evidence covers candidate b69214d against baseline b3a0d3a only; it was not rerun and does not constitute full regression for the new adapter. The suite is not all-green.

## 保留门禁 / Remaining gates

同步Python后端只能约束调用次数并拒绝迟到结果，不能强制中断任意阻塞callable；后端必须另实现硬时限。没有生产backend、OS证据collector、信任根配置或正式调度切换，host入口仍应禁用。路径与签名约束不证明生产ACL或唯一Inventory锁已接入。跨库提交仍需对账，不能用旧库覆盖UNKNOWN/预算。完整新候选回归及生产兼容尚待完成。

The synchronous callable is not forcibly interruptible; the backend must enforce a hard timeout independently. Production backend, OS evidence collection, trust provisioning and scheduler cutover are absent. Keep host admission disabled. Path/signature checks do not prove production ACLs or sole Inventory-lock integration. Cross-ledger commits require reconciliation; stale database restores must not erase unknown effects or budget history. New-candidate regression and production compatibility remain pending.

RELEASE_READY=false；PRODUCTION_DEPLOYED=false；PRODUCTION_ACCEPTED=false。下一步固定提交并完成新候选验证、依赖闭包及批准生产适配合同。报告仅包含合成测试、状态、源码哈希和测试摘要，无秘密或客户资料。

Release, deployment and production acceptance remain false. Next: pin the commit, validate the new candidate and complete dependency closure and authorized production adapter contracts. No secrets or customer data are included in this report.
