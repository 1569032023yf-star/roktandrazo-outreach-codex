# 原Inventory所有者排他修复 / Original Inventory owner exclusion repair

固定源码 / Fixed source: `4b0353cbc4a5c69998fdd597d2bb884f7f5da8d0`

原正式调用链为bd_orchestrator.stage_inventory → bd_db.acquire_run_lock；此前按日期及超时接管，跨日可能并行，异常finally还会释放未知副作用的锁。现同BEGIN IMMEDIATE检查全部Inventory日期，仅明确released可继续；空值、NULL、异常持有者均保留。SystemExit及业务异常均保留原锁，正常已知返回保留原释放合同。未知不会因时间、进程重启或相同holder而重放。
The actual owner call path is bd_orchestrator.stage_inventory → bd_db.acquire_run_lock. Previously date-scoped locks and timeout takeover could overlap across dates, while exception cleanup released locks despite unknown effects. The same BEGIN IMMEDIATE now checks every Inventory date, allowing only explicitly released rows. Empty, NULL and malformed holders remain blocked. SystemExit and business exceptions preserve the original lock; known normal returns retain the existing release contract. Time, process restart and repeated holders do not authorize unknown replay.

共享inventory_lock_blocked同时接入原owner、原Publisher及安装维护准入。初版68ec独审发现空值在安装准入仍被放行，现已修复并重新固定审核。未修改非Inventory锁的既有过期合同；未创建新锁系统、调度器或生产运行。
The shared inventory_lock_blocked predicate is connected to the original owner, original Publisher and installer maintenance admission. Independent review of initial 68ec found empty values still admitted installation maintenance; this was repaired before the current fixed review. Non-Inventory expiry behavior is unchanged. No replacement lock system, scheduler or production run was created.

## 验证 / Verification

当前候选组合245项，passed=True；独审详见INDEPENDENT_REVIEW.md及INDEPENDENT_RESULT.json，结论OFFLINE_SCOPED_REVIEW_PASSED。原SQLite及真实子进程退出/并发验证仅针对临时数据库；实际stage函数以AST隔离加载，业务Provider回调为替身，不证明真实业务采集。
Current fixed-candidate combined validation: 245 tests, passed=True. See INDEPENDENT_REVIEW.md and INDEPENDENT_RESULT.json for independent evidence, status OFFLINE_SCOPED_REVIEW_PASSED. Original SQLite logic and actual child-process exit/concurrency probes use temporary databases only. The actual stage function is AST-loaded in isolation with Provider callback doubles; this does not prove business collection.

可比全量：基线`cc6434e1fdff68c0069a5cd9a85fe22c4b9d994d`与当前候选各833项；基线37 failures/17 errors，候选37 failures/17 errors。NO_NEW_REGRESSION=True；ALL_GREEN=False。不继承旧候选结果。9cbc初次全量60失败/17错误，新增23项为当前异常释放旧预期及历史补丁读取演进源码；保留原诊断。当前入口保留未知锁，历史补丁改用原固定SHA字节夹具，未放宽产品门禁。
Comparable full regression: baseline `cc6434e1fdff68c0069a5cd9a85fe22c4b9d994d` and current candidate each ran 833 tests. Baseline has 37 failures/17 errors; candidate has 37 failures/17 errors. NO_NEW_REGRESSION=True; ALL_GREEN=False. Old-candidate results are not inherited. Initial 9cbc had 60 failures/17 errors: 23 added failures reflected outdated exception-release expectations and historical patch tests reading evolving source. That diagnostic is retained. Current unknown work remains fenced; historical tests use the original fixed-hash byte fixture without relaxing product gates.

## 制品 / Artifacts

真实AMD64宿主重新构建，71文件；Publisher支持包17文件，实际解压后新进程导入通过。新原owner companion精确绑定bd_db.py与bd_orchestrator.py，含两文件前后Git blob SHA；不扩大宿主白名单、不自动部署。安装包仍为工程包，正式backend未闭环，不能作为完整可安装发布版。全部文件摘要见ARTIFACT_MANIFEST.json。
The actual AMD64 host was rebuilt with 71 files. The 17-file Publisher support archive passed a fresh-process import after extraction. The updated original-owner companion binds bd_db.py and bd_orchestrator.py with before/after Git-blob hashes, without expanding the host allowlist or deploying automatically. Artifacts remain engineering archives: the formal backend is incomplete, so they are not a complete installable release. Every artifact hash is recorded in ARTIFACT_MANIFEST.json.

- install.zip SHA256: `9990cfa0179d2b54bd35602be976923e3d3f624652d49e38dd0a328a0436fdbd`
- rollback-tools.zip SHA256: `e9da70c05efb23fb299d4ffbfa08e646b3e5c1593080442976d101a37c305fd6`
- Host manifest SHA256: `f46ffb36566e511510d2fcf88e639b41667b363f78e9d0cf1a561bd8922f8f81`
- Publisher support SHA256: `372d61a6475c41a9761533dc916858d8c698b7baf4446c0bacbe0bc8927553db`
- Publisher manifest SHA256: `10188b161a70a35a382bf6fffa9e0a24b3d6975b4756fee10e3ea1d23419dfbc`

## 未完成及下一步 / Remaining work and next steps

继续正式backend与原Inventory所有者及服务事件消费者接线，复用原数据库锁并加入持久事件/预算/取消/结算合同；禁止用离线supervisor锁冒充原生产所有者。完成后重建完整发布版并做授权隔离Windows生命周期验收。
Continue formal-backend wiring to the original Inventory owner and service event consumer, reusing the original database lock with durable event, budget, cancellation and settlement contracts. An offline supervisor lease is not the original production owner. Then rebuild the complete release and perform authorized isolated Windows lifecycle acceptance.

WorkBuddy仅在完整候选、独审及明确授权后，对最终SHA验证真实PowerShell入口、Disabled/Stopped服务、非对称ACL、首装/升级/中断恢复/回滚及唯一Inventory排他。已提交P1证据不重复索要。当前不执行现场动作，生产数据库/账本/目录/ACL/服务/Inventory及现场发布器均未修改。
After a complete candidate, independent review and explicit authorization, WorkBuddy should verify the final SHA against the actual PowerShell entry, Disabled/Stopped service, asymmetric ACLs, first install/upgrade/interruption recovery/rollback and sole-Inventory exclusion. Previously submitted P1 evidence is not requested again. No site action was performed; production databases, ledgers, directories, ACLs, services, Inventory and Publisher remain unchanged.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`
