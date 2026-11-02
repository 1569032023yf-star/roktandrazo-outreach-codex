# U1 安装文件身份竞态修复 / Installer file identity race repair

更新时间 / Updated: 2026-11-02T21:04:43.642376+00:00
恢复本地与远端 / Recovery local and remote: 9eeeb88454255d9500761b5d6a6ded2fe31612aa
固定源码 / Source: 57bb0d1ccdd320e4c22d6a1e6e9982106b440ea1

中文：沿实际安装器到 host_file_transaction.read 调用链发现P0文件身份竞态：原先路径stat通过后，打开的句柄可能已经是被替换的另一个文件；原校验仅比较读前读后句柄，未绑定最初路径。现于读取字节前将句柄身份、大小、mtime及硬链接数与初始stat绑定，并重验普通路径；读取后对比句柄和最终路径身份，拒绝名字替换及新增硬链接。这不是完成全局TOCTOU防护或管理员ACL验收，目录保护和维护门禁仍必要。
English: The actual installer helper had a P0 stat/open race: stable reads of a substituted handle could pass. Before reading bytes, the opened handle now must match the initially checked identity, size, mtime and single-link count; the ordinary path is rechecked. After reading, handle and final pathname identities must still match. This does not establish global TOCTOU protection or administrator ACL acceptance; protected directories and maintenance admission remain required.

中文：新增两项可重复故障注入在真实文件系统的open边界替换名字或增加硬链接，均拒绝；实际安装包内host helper单独导入运行两项通过。完整文件生命周期单模块11项通过（54.228秒）；本轮组合定向结果见TARGETED.json及原始输出。新候选可比回归见下，失败ID相同不等于全绿。独审不可用，固定源码保持PENDING。
English: Two reproducible faults replace the name or add a hardlink at the real filesystem open boundary; both are rejected, also when importing the packaged host helper. The file lifecycle module passed11 tests in54.228s. Combined results and raw output are retained. Fresh comparable regression follows; identical failures do not mean all-green. Independent review remains PENDING for this pin.

定向 / Targeted: {"command": ["python", "-B", "-m", "unittest", "test_host_file_transaction", "test_host_install_transaction", "test_disabled_host_package"], "returncode": 0, "passed": true, "seconds": 105.477, "tests_run": 24, "runner_seconds": 105.19, "source_commit": "57bb0d1ccdd320e4c22d6a1e6e9982106b440ea1"}
回归 / Regression: {"baseline_commit": "9eeeb88454255d9500761b5d6a6ded2fe31612aa", "candidate_commit": "57bb0d1ccdd320e4c22d6a1e6e9982106b440ea1", "isolated_root": "C:\\Users\\15690\\AppData\\Local\\Temp\\u1-compare-7eklyl4k", "complete": true, "baseline_run": 833, "candidate_run": 833, "baseline_failures": 37, "candidate_failures": 37, "baseline_errors": 17, "candidate_errors": 17, "failure_ids_identical": true, "error_ids_identical": true, "all_green": false, "no_new_regression": true}
安装ZIP / Install SHA256: dbf21de5f7b1c88d4e26a69fd04995c552e6be824e34f2dd2888909ed47ff026
回滚工具ZIP / Rollback SHA256: 613ba94564509c33dbe93f85a487475473f937320ffe1302fc03c29fd5778978
外清单 / Manifest SHA256: 10630101294a1d685bac7586957ef78e9b718d2a57f931ce240a23ae3b27dadb
65文件逐SHA256、两ZIP成员字节及AMD64 PE核验通过。All65 file hashes, archive member bytes and AMD64 PE verified. The packaged host helper matches pinned source.

中文：已重读Issue2指令A、规范、本地canonical和checkpoint；起始tracked clean、远端匹配，无其他U1进程；保留旧recovery guard。自动化仍每3小时/45分钟预算/最多两重线；无硬超时字段，不宣称强制终止。WorkBuddy main仍10e269，复用既有6580465343消费回执，不重采、不重发合同或消费回执。原生产锁源码只读表明它以业务日期组成key、存在stale期限；不能把开发锁或一次快照冒充持续维护排斥。此缺口仍是下一动作，本轮没有解除上轮hard gate。
English: Re-read Issue2 directive A, repository rules, actual canonical and checkpoint. Recovery tracked tree was clean and remote matched; no concurrent U1 process, old recovery guard preserved. Existing3-hour automation/45-minute budget/two-heavy-line limit unchanged; no platform hard timeout claimed. WorkBuddy main remains10e269; existing receipt6580465343 reused without sampling or duplicate requests/consumption. Read-only original lock source shows date-key and stale semantics; development locks or snapshots cannot establish continuous maintenance exclusion. The prior hard gate remains intact.

下一步 / Next: 继续实现原生产 Inventory 权威维护排斥适配器；公开安装执行仍硬拒绝，维护集成和正式backend不声明完成。
Continue the original production Inventory maintenance exclusion adapter; public installation remains rejected, maintenance and formal backend integration remain incomplete.
DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false. 唯一原Inventory / Sole original Inventory:1784775229336.
无生产数据库/账本/服务/ACL/调度/配额/SMTP变更，无手动采集。No production DB, ledger, service, ACL, scheduling, quota, mail changes or manual collection.

工程回执已发布并精确回读 / Engineering receipt published and exact readback verified: https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/2#issuecomment-6588433431
