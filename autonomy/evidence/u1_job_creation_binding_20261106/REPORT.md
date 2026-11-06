# U1 创建时 Job 绑定 / Creation-time Job binding

中文：任务 rokt-razo-20261106T120615Z；开始 2026-11-06T20:06:29+08:00，工程完成 2026-11-06T12:11:14.217586+00:00。D 盘隔离树 u1-job-creation-binding-20261106；分支 codex/u1-job-creation-binding-20261106；起始 d3b61dd922f0e9f25bf890ec942c917cd6bf203c，固定源码 ed1f89fe95c7e5d4d955a632df895beac4c5e79c。主线和远端仍为 03c2ec44e1ca4d8b1b8d10841756ded13380f571，协调远端 a823c9c807565ad7087af1da1078736e0ab406d2。旧 C 路径 Junction 已核验指向 D 权威目录；主树 tracked clean，历史 untracked 和备份保留；canonical 可读。CURRENT_STATUS.md / FILE_MANIFEST.md 在主树不存在，未据此推断能力。本轮仅一条重型线。

English: Task/start/end, isolated D: worktree/branch, base and source revisions are pinned above. Main and coordination remote revisions were verified. The old C: Junction targets the authoritative D: workspace; tracked main files, historical untracked files and backups were preserved. Canonical was readable; two historical startup documents were absent, with no capability inferred from that absence. One heavy workstream ran.

中文：发现原 process_job 在 CreateProcessW 返回后才 AssignProcessToJobObject，监督进程在窗口内退出可遗留挂起子进程。本次通过 STARTUPINFOEX 的 JOB_LIST 属性在创建时绑定 kill-on-close Job；保留继承句柄白名单、挂起启动和现有生命周期/权限检查；创建后查询具体 Job 成员身份，通过后才恢复线程。属性不支持或设置失败不回退到不受控启动。身份查询失败按原合同清理；查询为否则直接终止挂起进程。没有新增调度器或生产安装。

English: Previously, assignment followed CreateProcessW, leaving a suspended-child ownership window. Creation now specifies the kill-on-close Job through STARTUPINFOEX JOB_LIST, retaining the handle allowlist, suspended start and existing lifecycle/authority checks. Explicit Job membership is checked before resume. Unsupported/failed attribute setup never falls back to uncontrolled launch. Failed membership queries use cleanup; negative membership directly terminates the suspended process. No scheduler or production installation was added.

中文：官方接口依据：[Microsoft UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)。该文档描述 JOB_LIST 的创建属性和 Windows 10 / Server 2016 起支持，不据此推断 API 调用内部遭强杀的所有事务保证。

English: The linked Microsoft API reference documents JOB_LIST and Windows 10/Server 2016 support. It is not used to infer transactional guarantees for a creator killed inside the API call.

中文：36 项组合通过（15 进程监督、11 协调、10 安装生命周期），39.748 秒。真实故障验证在 CreateProcessW 已返回、应用尚未记录 assigned/恢复线程时暂停，杀死监督进程后，挂起子进程消失且业务标记未执行；另验证 JOB_LIST 更新失败不执行子进程。既有超时树终止、句柄隔离、身份持久化失败、安装补偿、UNKNOWN 不重放保持通过。RESULT.json 和 controlled-run.json 保留命令、完整 SHA 与受控子进程回执；本轮未改源码后才固定提交，两份代码内容与测试时相同。未重复全量；没有新包，旧包不继承新源码验收。

English: All 36 combined tests passed in 39.748 seconds: 15 supervision, 11 coordination and 10 installer lifecycle checks. A real fault pauses immediately after CreateProcessW returns and before application bookkeeping/resume, kills the supervisor, verifies child disappearance and no business marker. Attribute rejection also prevents child execution. Existing timeout, handle, durable identity, compensation and UNKNOWN rules pass. Results and bounded-run receipt retain command/revision evidence; tested code is unchanged in the fixed source commit. No full suite or package was rebuilt, and old package acceptance is not inherited.

中文：仍未验证在 CreateProcessW 调用内部强杀、不同 Windows/宿主嵌套 Job 配置、全部聊天接入。独审 PENDING；不能自审代替。已真实使用现有本机合作槽及 Git 短锁，但未证明全局互斥/聊天硬停；240 秒只约束测试子进程。未修改主树 canonical/checkpoint：共同入口尚未全员接入，按用户 V2 保留独立分支成果；本分支队列明确只是投影。下一步对固定源码独审、核验共同入口后集成；随即继续 Provider/Worker 业务导入闭包，费用/终态缺合同仍 CONTRACT_MISSING。

English: In-call creator death, other Windows/nested-Job environments and universal chat adoption remain unverified. Independent review is PENDING. Cooperative local slots/Git locks were used, not global exclusion or a chat hard stop; 240 seconds bounded only the test child. Main canonical/checkpoint remain untouched until shared-entrypoint adoption permits safe integration, as allowed by V2; branch queue is only a projection. Next review the fixed source and shared entrypoint, integrate safely, then continue Provider/Worker import closure. Missing billing/terminal authority remains CONTRACT_MISSING.

中文：回退仅撤销独立分支源码提交 ed1f89fe95c7e5d4d955a632df895beac4c5e79c 回到上一固定版本，不运行生产回滚、不删状态。生产验证和完整安装包仍待完成。无生产数据库写入、Inventory 触发、邮件、服务安装、ACL 或配额改动。所有交付最终状态 false，BUSINESS_GROWTH=UNKNOWN；全部生产门禁 false。

English: Source rollback would revert only the isolated code commit to its preceding fixed revision; no production rollback or state deletion is run. Complete package and production acceptance remain pending. No production database, Inventory, email, service, ACL or quota operation occurred. All final delivery states/gates remain false; BUSINESS_GROWTH=UNKNOWN.
