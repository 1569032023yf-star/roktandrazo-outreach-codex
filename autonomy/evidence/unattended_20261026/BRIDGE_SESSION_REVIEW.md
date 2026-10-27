# 桥接会话证据独立审核 / Independent bridge-session evidence review

固定提交 / Pinned commit: `68802d52970861b52668251795fdbde16e17b44b`。

结论 / Verdict: **PASS_FOR_OFFLINE_BRIDGE_EVIDENCE_CONTRACT**。Reviewer未参与此提交实现；静态检查并独立执行`python -B -m unittest test_bridge_session_evidence -q`，13项通过，0.005秒，退出0。未修改源码或提交。

The reviewer did not implement this revision. Static inspection and an independent13-test run passed in0.005 seconds, exit0. No implementation edits or commit were performed.

## 核验范围 / Verified scope

- 配置、两个POST health观察及OS事件窗口均经可信消费者认证，并绑定配置、来源、身份及boot。窗口覆盖两个观察，序列连续，完整性、缺口和全部交互会话标记严格判断。
- Configuration, two POST-health observations and OS events are authenticated and bound to configuration, source, identity and boot. Coverage, sequence continuity, completeness and all-session assertions are checked.
- 跨登录要求严格中间时刻的旧logoff和新logon、相同用户，闭区间拒绝额外关联生命周期事件或boot。第二probe同秒logoff无法确定先后，测试确认拒绝。
- Cross-logon acceptance requires an ordered interior logoff/logon pair for the same user. The closed interval rejects extra associated lifecycle events and boots; a logoff at the second probe timestamp is rejected as ambiguous.
- 无人登录不能仅凭两个端点：还要求machine_boot配置、无需交互会话、从boot开始的完整事件覆盖、初始会话0且没有登录事件。HKCU Run不能替代这些条件。
- Login-free acceptance additionally requires machine-boot configuration, no interactive dependency, complete coverage starting at boot, zero initial sessions and no login events. HKCU Run alone is insufficient.
- acceptance_id由稳定观察事实产生，同一观察重签receipt不增加新的身份；evidence_digest保留传输证据差异。PROCESS_OBSERVATION明确端点实例相同或不同，不宣称连续存活。
- Stable acceptance_id survives receipt re-signing; evidence_digest preserves transport differences. PROCESS_OBSERVATION distinguishes same/different endpoint instances without claiming continuous availability.
- 返回固定分类与哈希，不泄露原始OS资料、URL或异常字符串；合成秘密污染测试通过。
- Outputs contain fixed classifications and hashes, without raw OS data, URLs or exception strings; synthetic secret-redaction testing passed.

## 保留限制 / Remaining limits

认证并不证明可信采集器的事实正确。生产Windows事件生产端、信任根配置、来源完整性与实际8791跨登录/无人登录观察尚未验收。此模块只返回观察范围结论，不持久计数；调用方仍必须按acceptance_id去重，并分别检查所需VERIFIED状态，不能以非空ID作为通过。没有网络请求、Windows操作、任务安装、生产数据库访问或全量回归。

Authentication does not prove collector truth. Production Windows collectors, trust provisioning, completeness and live8791 observations remain unaccepted. The module returns observation-scoped results without persistent counting. Consumers must deduplicate acceptance_id and check the required VERIFIED fields; a nonempty ID alone is not acceptance. No networking, Windows operation, task installation, production DB access or full regression occurred.

SCOPED_REVIEW_PASSED=true; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false。下一步集成计数消费者及正式只读证据合同，不将离线夹具升级为生产结论。报告自检：中英双语、范围及限制明确、无秘密或客户资料。

Next: integrate the counting consumer and approved read-only evidence contract, without promoting fixtures to live proof. Report self-check: bilingual, explicit scope/limits, no secrets or customer data.
