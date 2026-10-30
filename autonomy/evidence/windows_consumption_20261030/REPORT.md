# Windows证据消费与保留意见 / Windows evidence consumption and reservations

WorkBuddy固定提交 / Pinned commit: `54b79153adf8b8d6df1349e5ea78751bf244f24e`。沿用Issue2交付6517133750；未重复backend请求或创建第二交接通道。 / Existing Issue2 delivery6517133750 is used; no duplicate backend request or second channel.

| 文件 / File | 验证Git blob / Verified Git blob |
|---|---|
| WINDOWS_ENVIRONMENT_EVIDENCE_20261030.json | c2386c8fc10695c96a975a59fad7e0724ffc4649 |
| WINDOWS_ENVIRONMENT_EVIDENCE_20261030.md | a623e0173a6b0ce59d693e9c8514803a4602bfe3 |

中文：原始文件逐字保存source/；2份Git blob以Git对象头+原始bytes重算，JSON解析及声明rokt.windows_env_evidence.v1关键结构通过，双语文档实际读取。没有提供外部JSON Schema，不主张外部schema验证或独立生产重采。来源为WorkBuddy非提权Session1，只读观察，不构成批准。原文每项采样时间保留；报告生成15:10:15+08，Git API提交15:11:55+08，相隔100秒，生成早于提交，本批没有倒置。旧0b096948生成晚于提交64秒的差异仍单独保留，不能混同。

English: Original source bytes are preserved. Both blobs were recomputed with the Git object header; JSON parsing and required declared-schema structure pass, and the bilingual document was read. No external JSON Schema or independent production resampling is claimed. Provenance is WorkBuddy non-elevated Session1, read-only observation, not approval. Individual sample timestamps remain intact. Generation15:10:15+08 precedes Git API commit15:11:55 by100 seconds; this batch is not inverted. The earlier0b09694864-second inversion remains separate.

中文：接受7877新反向启动样本：helper08:48:23，GUI09:20:23，kernel09:20:24；生产方判NOT_SUPPORTED_OBSERVED。时间相邻和父子链不能证明GUI触发是唯一原因；无崩溃/SCM事件不能排除所有替代原因。HiberbootEnabled=1，不把LastBootUpTime自行升级为已证实冷启动。仅一批观察，不等于真实注销/无登录重启验收。当前交互转发204/200不证明无人登录出口；无GUI按需拉起、注销、混合启动、D盘可用性仍UNKNOWN。FailureActions不存在为生产方注册表观察，不授权修改。

English: Accept the new negative7877 startup sample: helper08:48:23, GUI09:20:23, kernel09:20:24; producer verdict NOT_SUPPORTED_OBSERVED. Temporal proximity and parentage do not prove GUI triggering is the only cause; missing crash/SCM events do not exclude every alternative. With HiberbootEnabled=1, LastBootUpTime is not upgraded to verified cold boot. This single sample is not real logoff/login-free restart acceptance. Interactive forwarding204/200 does not establish unattended egress. GUI-free demand start, logoff, hybrid startup and D-volume availability remain UNKNOWN. Missing FailureActions is an observation, not permission to modify it.

中文：8791无监听、pythonw为0、Run注册存在但未存活，BRIDGE_AUTOSTART_EFFECTIVE=false；历史锁owner已消失。未重启桥接或清锁，根因UNKNOWN。三项BD任务均Interactive/Limited，无人登录支持未成立。旧BDExecutionHost目标缺失，保持停止，不启动。

English:8791 has no listener, pythonw count0, and the registered Run entry has no surviving process: BRIDGE_AUTOSTART_EFFECTIVE=false. A historical lock owner is absent. No restart/lock deletion occurred; root cause UNKNOWN. Three Interactive/Limited BD tasks do not establish login-free operation. Keep the obsolete missing-target BDExecutionHost stopped.

中文：候选目录仍不存在，父/兄弟目录ACL只是先例，不能称目标生效ACL已通过。新提案“保持继承”与已审安装器关闭继承、仅SYSTEM/Admin/service精确ACE合同冲突；不静默覆盖，保留待独审/最小授权解决。SeServiceLogonRight仍exit740未知，生产方“非阻塞”意见不能关闭本地门禁。未提权、建账户/目录、改ACL/服务。安装独审57bccd47仅设计批准，仍缺持久安装日志/原子首次发布/维护租约实接。

English: Candidate roots remain absent. Parent/sibling ACL precedents are not the candidate's effective ACL. The new keep-inheritance proposal conflicts with the reviewed installer's protected SYSTEM/Admin/service-only ACE contract. Preserve this discrepancy for independent review and minimal authority; do not silently replace the contract. SeServiceLogonRight remains unknown behind exit740; a producer nonblocking opinion cannot close local gates. No elevation/account/directory/ACL/service changes occurred.57bccd47 approval is design-only; durable installation journaling, atomic first publication and actual maintenance-lease integration remain missing.

中文：发布器仍仅既有13个.py/最多6文件，不能承载7个非.py开发包、新文件、ABSENT备份或删除回滚。唯一Inventory1784775229336权威沿旧证据；guard10/10、rollback8/8是引用旧测试，不冒称本批重新运行。CURRENT_SAFE=UNKNOWN；本批没有新SAFE/城市/Provider/Inventory运行统计，不以旧65/城市状态推断当前。生产数据库、SMTP未被本轮写入或操作，未采集、部署或发送邮件。

English: The existing publisher remains limited to13 existing.py paths and at most6 files; it cannot deliver the seven non-.py package files, new files, ABSENT backups or deletion rollback. Sole Inventory1784775229336 authority follows prior evidence. Guard10/10 and rollback8/8 are referenced prior tests, not fresh executions. CURRENT_SAFE=UNKNOWN; this batch supplies no new SAFE/city/Provider/Inventory-run statistics, so older65/city results are not current facts. This cycle performed no production database/SMTP mutation, collection, deployment or email sending.

中文：本轮实际代码acdb1494补显式HTTP凭据期限与未知时钟拒绝，44组合通过，12固定文件/导入通过，独审PENDING；详见../host_http_expiry_20261030/REPORT.md。消费成功以同目录CONSUMPTION_RECEIPT.json中Issue2发布及独立逐字回读为准，发布前为false。

English: Actual codeacdb1494 adds explicit HTTP credential expiry and invalid-clock rejection;44 combined tests and12 pinned-file/import checks pass, review PENDING. See the adjacent engineering report. Consumption succeeds only after existing Issue2 publication and independent exact readback recorded in CONSUMPTION_RECEIPT.json; it remains false before then.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. production_installable=false; allow_dispatch=false; allow_cancel_dispatch=false.
