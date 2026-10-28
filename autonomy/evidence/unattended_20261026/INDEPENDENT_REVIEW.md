# U1固定源码独立复审 / Independent review of pinned U1 source

日期 / Date: 2026-10-28 (Asia/Taipei)
最终源码 / Final source: `3f03417ba46f565525b2b254fdbc559667ab96a9`
差异基线 / Diff baseline: `1c8a7fdbae8866f6eadd8de9fd935b873a5b5033`
结论 / Verdict: **PASS_FOR_SCOPED_OFFLINE_CANDIDATE**.

## 独立性与范围 / Independence and scope

本Reviewer未参与实现，仅只读审查固定差异、独立运行合成测试并编写审核报告。审核范围为growth_ledger预算对账修复、release_contract离线兼容合同及对应测试；组合测试覆盖已有slot、host、bridge、history、snapshot及rollback模块。此结论不能扩展为整体U1开发完成、正式backend接入、生产发布或无人登录验收。 / This reviewer did not implement code: work was limited to reading pinned differences, independently running synthetic tests and writing review reports. The reviewed change covers growth_ledger budget reconciliation, the offline release_contract and corresponding tests. Combined tests cover existing slot, host, bridge, history, snapshot and rollback modules. This verdict does not establish overall U1 completion, formal backend integration, production release or login-free acceptance.

## 发现、修复及复核 / Findings, corrections and verification

1. 初查发现可信签名但错误run_id的预算回执可以释放其他run预留；独立合成复现成功，记录于U1_REFRESH_REVIEW.md。09d65c修复后，settle对known及unknown回执均比较持久run，对claim绑定逐项严格比较类型与值，缺claim_hash或不匹配token哈希失败关闭；匹配检查在重复回执及状态更新之前。重开数据库后错误回执仍不释放预算；正确回执与幂等重复保持可用。 / Initial review reproduced a trusted signed receipt with the wrong run_id releasing another run reservation; U1_REFRESH_REVIEW.md records the reproduction. Revision09d65c compares persisted run for both known and unknown receipts, strictly matches every claim-bound type/value, and denies missing claim acknowledgements or mismatched token hashes before duplicate handling or state updates. Reopening does not release rejected reservations; valid and duplicate receipts still work.

2. 新合同初版接纳Windows设备路径及文件祖先冲突，独立复现CON、NUL.py、COM1.txt、AUX及a与a/b.py。3f03417拒绝每段设备名及扩展、大小写折叠的双向祖先冲突；既有绝对路径、穿越、空段、流、反斜杠和大小写同名拒绝保留。 / The initial contract accepted Windows device paths and file ancestor collisions; independently reproduced CON, NUL.py, COM1.txt, AUX, and a with a/b.py. Revision3f03417 rejects device stems/extensions in every segment and both directions of case-folded ancestor collisions while preserving absolute/traversal/empty-component/stream/backslash/case-collision checks.

3. 兼容合同必须与外部批准上下文逐项匹配，16项能力全部严格True才返回compatible；签名、身份、时间、源码/包/runtime/发布器指纹和目标存在/缺失合同均检查。任何结果都保持allow_install=false和allow_dispatch=false，不执行IO、注册任务、部署或采集。 / The compatibility contract must exactly match the separately approved context and all16 strict capabilities. It checks signatures, identity, freshness, source/package/runtime/publisher fingerprints and target hash/absence assertions. Every result retains allow_install=false and allow_dispatch=false; no IO, task registration, deployment or collection occurs.

## 实际独立测试 / Independently executed tests

固定源码独立执行111项，9.344秒，全部通过： / Independently executed111 tests against the pinned source in9.344 seconds; all passed:

```text
python -B -m unittest test_unattended_policy test_bridge_acceptance test_durable_slots test_growth_ledger test_growth_history_contract test_host_preparation test_single_slot_adapter test_bridge_session_evidence test_growth_snapshot test_rollback_admission test_u1_manifest_closure test_release_contract -q
```

此前对09d65c的44项独立测试3.595秒通过；初查旧源码93项6.748秒通过但额外故障复现仍发现缺陷，故测试通过不能替代失败路径审核。这里未独立运行全量suite，不声明全量全绿或最终NO_NEW_REGRESSION。 / Earlier44 independent tests against09d65c passed in3.595 seconds. The initial93 tests passed in6.748 seconds despite the independently reproduced defect, illustrating why passing tests cannot replace failure-path review. No full suite was independently run here; no all-green or final NO_NEW_REGRESSION claim is made.

## Git字节固定 / Pinned Git-blob hashes

| 文件 / File | SHA-256 |
|---|---|
| autonomy/growth_ledger.py | fc15509e9b97140304ed842e45b64be5953bdbcde1b1ffc63be38ef17e302c47 |
| autonomy/release_contract.py | 59a70cdd02e5032cf5f4a52cb139c9d0b5ac4454d1d918f3e654df70b98ffed8 |
| test_growth_ledger.py | 1487806487f55a3066c1d21a81b59d94c71326a90e6692f7cde633f101aa9448 |
| test_release_contract.py | a36100faeaae037524ddc82fc9cc2ddfffd0baff4d4647d16fdf4a0e960d18c2 |

## 未审与生产门禁 / Excluded scope and production gates

真实Windows证据生产端、正式Inventory有界执行/取消/回执合同、唯一生产锁接入、获准出口、身份及ACL、完整正式历史与规则映射、目标runtime和发布器指纹、实时备份/安全窗口均未获本次审核验证。签名仅证明来源；compatible仅代表合同计划一致，不证明实际能力。实际无人登录仍需获准窗口内至少两个连续自然周期及OS登录/启动审计。 / Actual Windows collectors, bounded formal Inventory execution/cancellation/receipt contract, sole production lock integration, approved egress, identity/ACLs, complete formal history/rule mapping, target runtime/publisher fingerprints and live backup/window gates remain outside this review. Signatures prove provenance; compatible means contract-plan consistency rather than actual capability. Login-free acceptance still requires at least two consecutive normal cycles plus OS boot/logon audits in an approved window.

旧执行器若不读当前账本不能恢复派发；保留UNKNOWN、预算和历史，不用陈旧数据库覆盖。此审核不授权管理员安装或生产切换。 / An old executor ignoring the current ledger cannot resume dispatch. Preserve unknowns, reservations and history without restoring stale databases. This review authorizes neither administrator installation nor production cutover.

生产副作用为零：未访问生产数据库、SMTP、采集来源或修改任务/权限；未发送GitHub消息。下一步主代理固定报告和清单、完成当前精确回归比较，并按既有GitHub合同等待/消费正式最小证据，不重复申请。 / Zero production effects: no production database, SMTP or collection-source access and no task/permission changes; no GitHub messages. Next the main agent should pin reports/manifests, complete the exact current regression comparison, and consume the existing GitHub contract evidence without duplicate requests.

报告自检通过：中英双语、实际测试/未执行、风险、数量、下一步明确；无客户原文、邮箱、Token、Cookie、代理秘密或凭据。 / Report self-check passed: bilingual, explicit actual tests/exclusions, risks, counts and next steps; no raw customer material, emails, tokens, cookies, proxy secrets or credentials.
