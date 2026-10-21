# 空间准入与离线交接独立审核 / Independent admission and handoff review

空间准入及离线双来源交接在限定范围通过独立审核；未发现阻止本次整合的问题。旧输出限制、锁恢复与清理发现不在本次关闭范围。

Storage admission and offline dual-source handoff pass independent review within scope; no blocking integration findings identified. Existing output-limit, lock-recovery and cleanup findings are not closed by this review.

审核时间 / Reviewed: 2026-10-21T00:39:57.753264+00:00
基线 / Baseline: 9af8a23596969dabd44e9ab57ef99ea6e03fa9ed

本次为手动续接独立审核，不计作新真实心跳周期。仅写本报告及对应JSON，不修改源文件、队列、状态或旧报告。
This is a manual follow-up review, not a new unattended heartbeat cycle. Only this report and its JSON were written; source files, queue, state and previous reports were unchanged.

## 核查结果 / Verified results

- 空间检查覆盖runtime、工作树、TEMP，每项未知或不足均拒绝；默认256 MiB余量加16 MiB提交预算，阈值验证及最近存在父目录处理正确。
- Storage admission checks runtime, worktree and TEMP; any unknown/low target rejects. Defaults are 256 MiB headroom plus 16 MiB commit budget, with validated thresholds and nearest-existing-directory handling.
- cycle在running租约及runner之前检查；拒绝不耗attempt、不新建lease、不调用runner；两次阻塞标记复盘，空间恢复后合成runner只执行一次。
- cycle checks before the running lease and runner; rejection consumes no attempt, creates no lease and invokes no runner. Two blocks mark reassessment; after space recovery the synthetic runner executes once.
- 交接只按source/provider_id分组，保留变化观测；域名相同仅提示潜在重复。官方站点/邮箱/组织/历史资格不从导入字段继承，历史保持UNKNOWN，邮箱只留证据，不进入合格business_email。
- Handoff groups only by source/provider_id and retains changed observations; shared domains only mark potential duplicates. Imported website/email/organization/history authority is ignored, history stays UNKNOWN, and observed emails remain evidence rather than qualified business_email.
- validate_handoff通过重新构造检查派生字段；重构不能证明来源真实性，package_sha256也是未验证的输入关联值。
- validate_handoff rebuilds conservative derived fields. Reconstruction does not prove source truth; package_sha256 is an unverified input reference.

## 独立测试 / Independent tests

21项通过：空间模块11项、cycle接线1项（LOW_SPACE/UNKNOWN及恢复）、交接9项。注入HEAD已提交process_job，未加载未提交启动器执行任务；没有真实代理、网络、生产DB或SMTP。
21 passed: 11 storage unit tests, 1 cycle integration test (LOW_SPACE/UNKNOWN and recovery), and 9 handoff tests. The committed HEAD process_job was injected; no real agent, network, production database or SMTP was used.

## 边界 / Limits

空间检查是快照，不是磁盘预留；检查后仍可能ENOSPC。

Space checks are snapshots, not reservations; ENOSPC can still follow admission.

URL校验是导入结构校验，不是DNS/重定向SSRF防护或官网所有权证明。

URL checks validate imported structure, not DNS/redirect SSRF protection or website ownership.

未复跑全部45项父测试，独立运行其中21项；未更改三个旧候选文件。

Independently ran 21 tests, not the entire parent 45-test suite; three historical candidate files were unchanged.

未验证实采真实性、生产发布、发送资格或无人值守周期。

No live collection truth, production release, send eligibility or unattended cycle was validated.

本次可关闭前份审核R1的“缺少空间预检”实现缺口；其余可靠性发现仍开放，AUTONOMOUS_OPERATIONS_ACTIVE仍不能据此设为true。
This closes the prior R1 implementation gap for missing space preflight only. Other reliability findings remain open; AUTONOMOUS_OPERATIONS_ACTIVE cannot be promoted on this basis.
