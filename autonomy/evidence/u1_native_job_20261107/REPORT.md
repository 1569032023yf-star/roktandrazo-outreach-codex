# 原生宿主创建时 Job 绑定 / Native host creation-time Job binding

Task: rokt-razo-20261107T120935Z. Start: 2026-11-07T20:09:51.1829104+08:00; checkpoint: 2026-11-07T12:22:38.232493+00:00.
Workdir: D:\CODEX\roktandrazo-workspace\u1-native-job-20261107. Git:2.54.0.windows.1. Start SHA:0965a26fcce2410cea94acd486e2413d9da6bd0f. Fixed source:4fc6db7c22e16885d68b81e7309d51286e7609b7.

中文：真实原生宿主原先先创建挂起Python、再加入Job；父进程在两步间崩溃可留下未受Job监督的子进程。本轮通过STARTUPINFOEX/PROC_THREAD_ATTRIBUTE_JOB_LIST在CreateProcess内部绑定非继承、关闭即终止的Job；恢复线程前验证归属。属性不支持或归属不明即拒绝，不回退。finally释放属性内存和线程句柄。
English: The native host previously created suspended Python before Job assignment, leaving an orphan window on host death. Creation now binds a non-inherited kill-on-close Job through STARTUPINFOEX/PROC_THREAD_ATTRIBUTE_JOB_LIST. Membership is verified before resume; unsupported attributes or uncertainty fail closed without fallback. Attribute memory/thread handles are released in finally.

依据 / Basis: [Microsoft Job creation example](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812), [attribute lifecycle](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-initializeprocthreadattributelist).

中文：20项组合通过（12.099秒）：真实x64编译、正常停止和父进程退出均清理子孙；创建后归属检查前退出清理挂起子进程；不支持属性在创建前拒绝。故障注入只在隔离编译测试副本中，无生产调试入口。另直接引用新包提取的EXE，两项生命周期核验通过（1.033秒）。首次夹具错误覆盖已固定输入，2项失败；改为独立输出后20项全过，保留失败运行记录。
English:20 combined checks passed in12.099s: real x64 compilation, descendant cleanup on disposal/parent death, suspended-child cleanup before membership check, and pre-creation rejection of unsupported attributes. Instrumented failure builds are isolated; no production debug entrypoint exists. Two further lifecycle checks directly reference the extracted package EXE (1.033s). Initial fixture writes targeted a pinned input (two failures); separated output fixes the fixture, with failed receipt preserved.

中文：新真实CPython包5058文件摘要通过，4960宿主回滚组件与安装字节一致。五个提取后离线探针/最终完整性VERIFIED；受控回执113.910秒，实际引导解析2.874秒。未运行安装/回滚脚本，归档匹配不代表现场恢复验收。
English:Fresh real-CPython archive:5058 digests pass,4960 host rollback components match installation bytes. Five extracted offline probes/final integrity VERIFIED; controlled receipt113.910s, bootstrap resolution2.874s. Install/rollback scripts were not executed; archive equality is not site restoration acceptance.

Install ZIP SHA256:7cb252758305d5491db128eacb6f83c1588c95fa7c05df1de052737ec7931420
Rollback ZIP SHA256:065a4cc1cb4f4d3403750dca452687f47028cd80e4ed912494166bafd07c95cd
Manifest SHA256:2d61d7f5ce57da9e772c733be8cc8ad6c9ba754a11fc002e6262869704928309
Native EXE SHA256:50c66942ee1a671b78fdcf84c9af20f76629eaa441254e69a67a0cf1f5810976

中文：独审PENDING，未以自审代替。主树/远端仍03c2ec44e1ca4d8b1b8d10841756ded13380f571，canonical可读但未写；多聊天共同接入未证明，故只更新隔离投影和checkpoint，不并发修改主树。C旧路径Junction指向D已核验，备份未动。使用合作锁及180/240/300/600/120秒子进程期限，不声称全局锁或整轮聊天平台硬截停。
English:Independent review PENDING. Main/remote remains03c2ec44e1ca4d8b1b8d10841756ded13380f571. Canonical is readable but unchanged because cross-chat shared entry adoption is unproven; only isolated projection/checkpoint updated. C-path Junction points to D; backups untouched. Cooperative locks/child deadlines used, without global lock or whole-chat hard-timeout claims.

中文：DEVELOPMENT_COMPLETE=false；RELEASE_READY=false；PRODUCTION_DEPLOYED=false；PRODUCTION_ACCEPTED=false；BUSINESS_GROWTH=UNKNOWN。allow_install/allow_dispatch/allow_cancel_dispatch/SMTP均false。无SCM服务启动、生产采集或第二Inventory。Provider权威费用/终态/取消回执仍CONTRACT_MISSING。下一步：业务启动参数与导入闭包，固定源码及包独审，共同协调确认后主线集成。
English:Overall development/release/deployment/acceptance false; business growth UNKNOWN. All installation/dispatch/cancel/SMTP gates false. No SCM service, production collection or second Inventory started. Formal Provider cost/terminal/cancellation evidence remains CONTRACT_MISSING. Next:business startup/import closure, fixed candidate independent review, then coordinated main integration.
