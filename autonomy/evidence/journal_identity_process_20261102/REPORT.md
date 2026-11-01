# U1日志对象与进程故障合同 / Journal object and process fault contracts

实际开始2026-11-02T07:48:25.6906209+08:00，触发2026-11-01T23:48:18.892Z。恢复实际本地/远端HEAD5eabe5cb92d96c1b4500185706ba8eb5dc4fa8a6，本地canonical可读。核验分支、origin、主/宿主工作树、既有锁、进程、代理变量名；没有另一repo匹配进程。原未跟踪取消证据/宿主5项文件保留，合法recovery guard不删，cycle锁结束按所有权释放。历史附件错误路径不存在，正确.codex路径存在，不将旧状态覆盖当前。会话无硬时限API，测试外层timeout120s/child20s，未建系统任务，在45分钟内结束。

Actual start/trigger and real recovery HEAD above. Local canonical read and branch/origin/worktrees/locks/processes/proxy names checked. No matching competing worker. Existing untracked work and recovery guard preserved; own cycle lock released. Attachment typo absent/correct path present, historical facts do not override current state. No session hard-limit API; bounded tests, no new system task, finish within45 minutes.

## 本轮实质进展 / Substantive progress

固定候选23c872eab5e8138ca8f42596508223251af7e21b仅新增3项真实Windows文件/子进程测试，不修改运行源码（运行实现仍41ab0b7）。1）writer打开时os.replace真实拒绝，关闭后替换成功，status仍禁止重放；2）创建硬链接后nlink2，writer拒绝写入，即使删除alias仍永久停用；3）child在STAGE效果后追加并fsync损坏记录，检测到内容修改后os._exit(47)，parent状态UNKNOWN/null pending，原INTENT与损坏字节保留；STAGE效果存在、PUBLISH不存在，相同operation重新进入CREATE_NEW拒且无新效果。

Pinned candidate adds3 actual Windows file/process tests only; runtime source unchanged. Open writer denies real os.replace, releases at close; real hardlink triggers irreversible stop even after removal; child appends/fsyncs corruption after STAGE effect, detects mutation and exits47. Parent observes UNKNOWN with no confirmed prefix, retains raw intent/corruption, sees STAGE only and rejects same-operation replay without any adapter call.

初次定向20项1失败：测试误将损坏JSON流的pending推定为STAGE；现有inspect先解析整流，损坏时UNKNOWN/null是实际合同。仅改测试为保留原INTENT字节、不虚构结构化前缀，未改实现“配合测试”。最终20定向1.089s与121组合7.497s全部通过，新增进程退出20s上限；命令/失败/修正记录见TEST_OUTPUT。旧833既有回归不重复也不继承，不宣称新候选全量全绿。

Initial targeted run failed because the test inferred a STAGE prefix from malformed JSON. Existing inspector parses the stream first and returns UNKNOWN/null; assertion corrected to preserve raw evidence without inventing a confirmed prefix. Implementation unchanged. Final20 focused/121 combined tests pass; command/failure history recorded. No inherited833 full-suite result or all-green claim.

## 审核、发布与证据 / Review, release and evidence

独立Reviewer不可用，PENDING；自检不能代替独审，旧079792aa仅状态读取范围独审不覆盖本候选。Windows测试结果限本机，不证明ACL、命名空间永久不可变、可信维护租约、正式安装backend或成功持源发布。打开writer的替换拒绝不证明关闭后的日志防篡改；stat/content检查也不排除检查间隙竞态。

Independent review PENDING; self-check and historical status-layer review do not cover this pin. Machine-local tests prove no ACL/immutable namespace/formal lease/backend/held-source publication acceptance. Open-writer denial does not protect a closed journal; checks do not eliminate races.

WorkBuddy main本轮远端核验仍13d061a82568bc147efa689742a61b3e06d95a31，无新证据，不重复Issue2回执6561646296或backend合同。既有消费8文件与3份内嵌摘要保留意见沿用：SAFE68、严格增长UNKNOWN，Inventory7firing/5真实run、零漏跑UNKNOWN；8791仅session健康，跨登录无人登录未通过；7877非交互出口UNKNOWN。生产采集/DB/SMTP访问、部署、服务/ACL/调度/代理修改均0，未重复apply。

WorkBuddy remote unchanged; reuse exact-readback receipt without duplicate. Existing evidence reservations and UNKNOWN growth/zero-miss/unattended facts retained, not resampled. No production collection/DB/SMTP access, deployment, OS/ACL/scheduler/proxy changes or release reapply.

发布清单为新增测试、本报告/manifest/test记录、queue投影和checkpoint；备份/恢复基线5eabe5c，必要时审核后的离线revert，不删除证据、不修复/重放UNKNOWN，无生产回滚授权。canonical本地autonomy/runtime/queue.json与Git投影分别更新并回读，不以投影替代本地队列。

Release scope is test/evidence/state only; recovery baseline5eabe5c, reviewed offline revert if required, preserve UNKNOWN evidence without repair/replay or production rollback authority. Local canonical and Git projection updated/read back separately.

下一项：离线inspect_install的操作/manifest/lease绑定、畸形字段与有界读取合同；固定源码独审PENDING。既有取消费用绑定/reserve-before-intent不重实现；正式Windows身份/ACL/lease/backend与无人登录周期仍阻塞。

Next: offline inspector operation/manifest/lease binding, malformed-field and bounded-read contracts; pinned independent review pending. Existing cancellation/reserve-before-intent implementation preserved. Windows identity/ACL/lease/backend and unattended cycles remain blocked.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN; allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.
