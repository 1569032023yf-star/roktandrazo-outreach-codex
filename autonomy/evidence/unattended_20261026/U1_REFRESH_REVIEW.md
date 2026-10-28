# U1刷新独立审核 / U1 refresh independent review

审核固定源码 / Reviewed revision: `1c8a7fdbae8866f6eadd8de9fd935b873a5b5033`.
结论 / Verdict: **CHANGES_REQUIRED_FOR_BUDGET_RECEIPT_BINDING**.

## 执行结果 / Executed results

独立运行93项组合测试，全部通过，耗时6.748秒；覆盖slot、growth/history、host、single-slot adapter、bridge session、snapshot、rollback及隔离包导入。该结果不是全量回归或生产验收。 / Independently ran93 scoped tests; all passed in6.748 seconds across slots, growth/history, host, single-slot adapter, bridge sessions, snapshots, rollback and isolated imports. This is neither full regression nor production acceptance.

## P1：预算回执未绑定持久run / Budget receipt does not bind the persisted run

`autonomy/growth_ledger.py`的`settle()`只按request_id读取预留，不核对回执run_id，也不直接检查已存claim绑定。独立合成复现：预留a的6单位全部预算后，提供同一request_id、错误run_id、可信签名、known且actual=0的回执，得到SETTLED；随后新请求b的6单位全部额度获准RESERVED_NOT_DISPATCHED。这允许错误关联的对账记录释放未知副作用所占预算。 / `settle()` selects reservations by request_id without comparing receipt run_id or directly checking persisted claim bindings. Independent synthetic reproduction reserved all6 units for request a, then supplied a trusted signed known receipt with the same request_id, a wrong run_id and actual=0. Settlement returned SETTLED and a new6-unit request b was admitted. A misassociated reconciliation receipt can therefore release budget held for uncertain effects.

SingleSlotAdapter.reconcile已有额外绑定检查，阻止其正常路径上的这一错配；但公开账本API本身缺少防护，不能把adapter检查当作账本不变量。 / SingleSlotAdapter.reconcile has additional binding checks protecting its ordinary path, but the public ledger API itself lacks the invariant.

建议：settle必须核对持久run；claim绑定非空时同时核对inventory/slot/epoch/owner/run/request及已持久claim哈希。缺失或错误字段应在事务更新前失败关闭。补充错误run、遗漏绑定、错误token和正常重复回执测试。 / Require persisted-run equality inside settle. For claim-bound reservations also match inventory, slot, epoch, owner, run, request and persisted claim hash. Missing or conflicting fields must fail before updates. Cover wrong runs, missing bindings, wrong tokens and normal duplicate receipts.

## 已核实边界 / Confirmed boundaries

01:00的上海业务日边界来自既有outreach_batch_date，bd_orchestrator委托该实现；本次不将其列为新缺陷，不建议擅改。签名只确认来源，不能确认OS事实。禁用宿主仍无生产派发能力。正式backend、真实OS/网络证据生产端、生产runtime指纹、新文件发布器及唯一调度权威切换仍未完成。 / The Shanghai01:00 business-day boundary comes from the existing outreach_batch_date used by bd_orchestrator; it is not classified as a new defect and should not be changed implicitly. Signatures prove provenance rather than OS truth. The disabled host cannot dispatch production work. Formal backend, actual OS/egress collectors, runtime fingerprints, new-file publisher support and sole-authority cutover remain incomplete.

## 未执行、风险与下一步 / Exclusions, risks and next steps

本Reviewer未修改实现，未访问生产数据库、网络来源、SMTP、系统任务或权限，未发送GitHub消息。未对未修复的源码给出通过结论；修复后须独立复审最终固定差异。 / This reviewer changed no implementation, accessed no production database, collection source, SMTP, scheduled task or permission, and sent no GitHub message. No pass is awarded to the unfixed source; independently re-review the pinned correction.

报告自检：中英双语、实际执行及未执行范围、数量、风险、下一步明确；仅合成标识，无客户资料、代理或凭据。 / Self-check: bilingual, explicit executed/excluded scope, counts, risks and next steps; synthetic identifiers only, no customer data, proxy secrets or credentials.
