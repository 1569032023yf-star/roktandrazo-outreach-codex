# U1 实际进程持久凭据 / Actual durable process evidence

固定源码 / Fixed source: `2db72ad5a016d24907e60c4481ffba1b870c959d` | 2026-11-03T02:58:45.114559+00:00

## 已完成工程 / Implemented engineering

原Windows Job监督器增加受信内部生命周期记录接口：LAUNCH_INTENT先持久记录命令摘要、随机Global Job名及监督进程PID/创建时间；子进程挂起创建并成功加入kill-on-close Job后，持久保存实际句柄读取的PID、创建FILETIME和镜像路径，之后才能Resume。只有整树终止、输出读取器关闭、句柄清理均已核验才写STOPPED。记录与原维护会话及命令精确绑定，使用原system_config事务和独立前缀的哈希链，不创建第二调度器，不改变原Inventory执行权。
The existing Windows Job supervisor now exposes a trusted internal lifecycle sink. LAUNCH_INTENT durably records the command digest, random Global Job name and supervisor PID/creation time. After suspended creation and successful kill-on-close Job assignment, actual process-handle PID, creation FILETIME and image path are persisted before Resume. STOPPED is written only after verified tree termination, closed output readers and handle cleanup. Hash-chained records bind the original maintenance context and exact command in the existing system_config transactions under an independent prefix. No second scheduler or change of Inventory ownership is introduced.

终态核验器已在真实PowerShell协调器首装、升级、升级回滚和首装回滚的隔离集成中，改用实际进程持久凭据确认终止。确认进程结束不代表安装成功，也不单独释放维护权；仍需文件/日志/SCM/ACL终态核验和原会话原子释放。
Isolated integration of the real PowerShell coordinator now supplies actual durable process proof to the terminal verifier across first installation, upgrade, upgrade rollback and first-install rollback. Process termination is not installation success and does not release maintenance ownership by itself; file/journal/SCM/ACL verification and the original atomic session release remain mandatory.

监督进程突然退出后，显式只读恢复同时核对原监督进程身份已结束、随机Job对象不存在、原子进程实例已结束；PID复用通过创建FILETIME区分，访问拒绝或未知均停保留。成功后仅追加终止凭据，不启动、终止、重放安装或释放维护权。STOPPED记录可跨进程重读。
After supervisor death, explicit read-only reconciliation requires the original supervisor instance to be gone, the random Job object absent and the original child instance ended. Creation FILETIME distinguishes PID reuse; denied access or uncertainty stops and preserves. Success appends termination evidence only: it never launches, kills, replays installation or releases ownership. Persisted STOPPED evidence survives process restart.

## 固定源码测试与独审 / Fixed-source tests and independent review

组合 **208项通过 / 268.814秒**；0 failures/errors/skips。完整输出与分进程host/authority结果在validation。独立审核另跑 **26项通过 / 89.16秒**，另 **4个隔离探针通过**；结论仅OFFLINE_SCOPED_REVIEW_PASSED，详情INDEPENDENT_REVIEW.md及JSON。
Combined validation: **208 passed / 268.814 seconds**, zero failures/errors/skips. Full output and separate host/authority results are under validation. Independent review separately ran **26 passing tests / 89.16 seconds**, plus **4 passing isolated probes**. Approval is OFFLINE_SCOPED_REVIEW_PASSED only; see INDEPENDENT_REVIEW.md and JSON.

新增实际覆盖：身份和STOPPED持久化；超时保留维护权；CONTAINED提交后Resume前异常不执行子进程动作；LAUNCH-only未知不重放；真实监督进程被终止后的只读恢复；实际安装协调器接实际终止凭据。独审额外验证STOPPED写入失败、原监督进程仍存活、不同命令绑定拒绝，以及父进程死亡后实际孙进程PID终止读回。开发首轮18项和父死专项1项通过后，最终源码重新运行全部组合，未继承旧SHA测试。
New actual coverage includes durable identity/STOPPED, retained exclusion on timeout, no child action after a failure between CONTAINED commit and Resume, LAUNCH-only uncertainty without replay, read-only reconciliation after real supervisor termination and the real installer coordinator using actual process proof. Independent probes additionally verify failed STOPPED persistence, refusal while the original supervisor lives, wrong-command binding and actual grandchild termination after supervisor death. An initial 18-test development run and one parent-death probe passed; final fixed-source combined validation was rerun rather than inheriting results from an old SHA.

## 限制、剩余工程与交付状态 / Limits, remaining work and delivery status

LAUNCH_INTENT之后缺少CONTAINED身份时严格UNKNOWN/STOP_AND_PRESERVE，不能猜测从未启动。CreateProcess到AssignJob之间突然退出可能留下未分配的挂起进程；当前不证明该窗口整树清理或自动恢复。lifecycle/record为受信内部接口，正式适配器必须固定命令、包和运行时镜像字节，不能接受调用者自报安全终止。SCM/ACL成功路径仍为隔离替身，真实Job/文件/SQLite证据不能充当生产服务验收。
Missing CONTAINED identity after LAUNCH_INTENT is strictly UNKNOWN/STOP_AND_PRESERVE, never assumed unstarted. Death between CreateProcess and AssignJob can leave an unassigned suspended process; this version does not prove tree cleanup or automatic recovery for that window. Lifecycle/record are trusted internal interfaces. The formal adapter must pin commands, package and runtime-image bytes instead of accepting a caller's claimed safe termination. Successful SCM/ACL paths remain isolated doubles; real Job/file/SQLite evidence does not establish production service acceptance.

完成正式固定安装命令、包及运行时镜像身份固定和原认证/seal接线，再执行完整调用链独审；冻结完整AMD64安装包后重跑生命周期和可比全量回归，授权前保持生产门禁关闭。
Complete the formal fixed install command, package/runtime-image identity pins and original authentication/seal wiring, then review the complete chain; freeze the complete AMD64 artifact and rerun lifecycle/comparable regression while production gates remain closed pending authorization.

此SHA尚无完整新AMD64安装包及package manifest SHA256，833项可比全量回归未重跑；旧包、审核和回归不继承。历史37 failures、17 errors不是全绿。完整候选、全链审核和授权后，WorkBuddy再按最终SHA核验真实无人值守首装、升级、进程/回滚中断恢复及Disabled/Stopped终态，不重复索要已消费P1证据。本轮不部署。
No new complete AMD64 package/package-manifest SHA256 or comparable 833-test full regression exists for this SHA; old artifacts, reviews and regression evidence are not inherited. Historical 37 failures and 17 errors are not all green. After the complete candidate, full-chain review and authorization, WorkBuddy should verify unattended first installation, upgrade, interrupted process/rollback recovery and Disabled/Stopped state against the final SHA, without repeating consumed P1 evidence requests. No deployment occurs now.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

本轮仅离线源码、临时隔离进程/文件/SQLite，未修改生产数据库、账本、ACL、目录、服务、Inventory、代理、注册表、任务、执行策略或现场发布器。接受既定非对称ACL裁决。目标仍在执行，不将组件范围审核充作完整交付。
Only offline source and isolated temporary processes/files/SQLite were used. No production database, ledger, ACL, directory, service, Inventory, proxy, registry, task, execution policy or site publisher was modified. The asymmetric ACL ruling remains accepted. The goal remains active; scoped component review is not complete delivery.
