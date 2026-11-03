# U1 安装器逐步维护权连接 / Installer per-step maintenance connection

固定源码 / Fixed source: `b4332e4e2144c36076849ecd5315eeae758ee56a` | 2026-11-03T02:29:42.003922+00:00

## 实际完成 / Implemented

真实PowerShell内部协调器的AssertHeld调用，经私有stdio请求父进程，在原SQLite维护会话所属线程核验Inventory/source/manifest/目标事务/动作和执行阶段；只有匹配本次序号的严格True确认才能继续。请求长度、数量、队列和输出有界；未知、重复、重叠、截断或错误绑定均停止并保留，不释放维护标记。没有新监听端口、第二调度器、任意路径或对外安装授权。
The real internal PowerShell coordinator sends AssertHeld checks through private stdio to the original SQLite session's owning thread. Inventory/source/manifest/target/action/executing phase must match; only a strict True acknowledgement for the current sequence permits continuation. Request size/count, queue and output are bounded. Unknown, repeated, overlapping, torn or mismatched requests stop and preserve exclusion. No listener, second scheduler, arbitrary path or public install grant was introduced.

ACK写端非阻塞，子进程不读回复不能挂住父进程deadline。Windows使用显式HANDLE_LIST，仅继承本次三个标准流句柄；进程挂起创建、加入Job后才恢复，父死仍整树终止。新helper纳入包内脚本SHA和构建源码固定检查；公开Execute hard拒绝保持不变。
Nonblocking acknowledgements prevent a nonreading child from hanging parent deadlines. Windows uses an explicit handle list containing only the three standard streams. Children are created suspended and resumed only after Job containment; parent death kills the tree. The helper is included in package hashes and fixed-source build checks. Public Execute remains hard rejected.

## 发现与修复 / Finding and fix

独审复现了读取线程已判CONTROL_OVERLAP后，队列中的旧请求仍可能收到ACK的竞态。已改为不可恢复的失败状态，读取失败与ACK使用同一把锁；耗时权威检查后、发送ACK前同锁复验。已知失败前后及handler期间失败均有零ACK负例。不以维护标记仍held为理由忽略该问题。
Independent review reproduced an acknowledgement race after the reader had already rejected overlapping requests. Sticky failure and a shared reader/ACK lock now recheck after the authority callback, immediately before sending. Negative tests cover known and callback-time failures with zero acknowledgements. A retained maintenance marker is not used to dismiss this issue.

## 当前源码证据 / Current-source evidence

- 组合 **195 PASS / 173.024s**；失败、错误、跳过均0。证据final/TARGETED.json和完整输出，按host/authority分进程保持开发护栏。
  Combined **195 PASS / 173.024s**, zero failures/errors/skips. See final/TARGETED.json and full output; host/authority groups remain isolated without relaxing development guards.
- 独审 **43项通过，另2项隔离探针**；仅OFFLINE_SCOPED_REVIEW_PASSED，完整调用链审核未完成。详情INDEPENDENT_RESULT.json及双语审核报告。
  Independent review: **43 tests passed plus 2 isolated probes**, scoped approval only; complete-chain review remains unfinished. See INDEPENDENT_RESULT.json and the bilingual review.
- 真实IPC连接真实协调器和临时SQLite，执行实际文件事务；SCM、ACL和管理员准入仍为隔离替身，不冒称实际Windows安装/ACL验收或正式最终核验器。
  Real IPC connects the real coordinator to temporary SQLite and actual file transactions. SCM, ACL and elevation admission remain isolated doubles; these results do not claim real installation/ACL acceptance or a formal terminal verifier.

中间193项表面通过的输出保留在validation；因运行期间源码修复，仅作DIAGNOSTIC_SOURCE_CHANGED_DURING_RUN。初次IPC测试曾读取空日志导致夹具IndexError，已修复；PID观察夹具也改为完整写入后原子公布，避免监管在JSON写完前终止进程。最终固定源码重新测试，不将这些中间结果记为通过。
The intermediate superficially green 193-test output remains under validation but is diagnostic only because source changed during execution. An initial fixture read an empty journal and raised IndexError; it was fixed. The PID fixture now atomically publishes complete JSON so supervision cannot kill it before publication finishes. Final fixed source was rerun; intermediate results are not counted as acceptance.

## 剩余工程与WorkBuddy下一步 / Remaining work and WorkBuddy next step

完成固定命令/进程身份的受控安装适配、启动及终止持久凭据和独立文件/日志/SCM/ACL终态核验器；再对完整认证调用链独审，冻结安装包并重跑生命周期及可比全量回归。
Complete the pinned-command/process-identity installer adapter, durable launch/termination evidence and independent file/journal/SCM/ACL terminal verifier; then review the full authenticated chain, freeze artifacts and rerun lifecycle/comparable regression tests.

正式Publisher认证/seal到固定安装命令的接线、真实进程实例的持久身份/终止证明、独立SCM/ACL/文件/日志终态核验尚未完成。当前没有新AMD64安装包和包manifest SHA，也未重跑833项全量；旧包与旧回归不能移植给此SHA。历史37 failures/17 errors不是全绿。
Supported publisher authentication/seal to the fixed installation command, durable real-process identity/termination evidence and independent SCM/ACL/file/journal terminal verification remain incomplete. No new AMD64 package/package-manifest hash or 833-test full regression is claimed for this SHA. Prior artifact/regression results are not inherited; historical 37 failures/17 errors are not all green.

WorkBuddy需在完整候选、全链审核及授权后，按最终SHA验证Windows无人值守首装、升级、进程退出恢复和回滚中断；目前不执行现场安装，不重复索要已消费的P1证据。生产部署和业务采集验收在其后。
After the complete candidate, full-chain review and authorization, WorkBuddy should verify unattended Windows first installation, upgrade, process-death recovery and interrupted rollback against the final SHA. No site installation now and no repeated P1 evidence request. Production deployment and business collection acceptance follow later.

## 状态与边界 / Status and boundaries

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

本轮仅开发副本及隔离临时进程/文件/SQLite；未修改生产数据库、账本、ACL、目录、服务、代理、注册表、系统任务、现场发布器或Inventory。无服务注册/启动、无SMTP、无客户数据或凭据提取。目标仍在执行，不能将范围审核描述为最终交付。
This run used development copies and isolated temporary processes/files/SQLite only. No production database, ledger, ACL, directory, service, proxy, registry, system task, site publisher or Inventory change occurred. No service registration/start, SMTP, customer-data or credential extraction occurred. The full goal remains active; scoped review is not final delivery.
