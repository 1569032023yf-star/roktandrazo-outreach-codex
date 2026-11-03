# 原stage事件链固定候选独审 / Pinned original-stage event-chain review

结论 `OFFLINE_SCOPED_REVIEW_PASSED`，固定 `3fbaa5ec42cb0655ecd1c811ccd8d02b1fc837bb`，基线68788653c848659c63f85021075fedee4aca5b13。原dea9报告保留诊断，本次新固定源码独立重跑。范围内无未解决阻断，`RELEASE_READY=false`，formalbackend与派发门禁仍false。

Conclusion: scoped offline review passed for the pinned source. The dea9 report remains diagnostic; this candidate was independently rerun. No unresolved blocker was found within scope. This is not release, deployment or formal Provider approval.

## 调用链与事务复核 / Call-chain and transaction review

只读审查实际源码：OriginalStageEvent匹配原DB/holder/日期/incarnation及running/live原job；固定event字节经ExistingOwnerBridge进入真实HTTP、原owner准入、单次event/claim持久join，再由原slot/budget协议执行与结算。实际stage不二次取锁、不回退legacy body；COMPLETED仍另读SAFE判断target，UNKNOWN保留原锁。默认原stage路径不变，无新增CLI开启或调度器。

Actual source was reviewed across the trusted stage wrapper, original job/owner identity, immutable event bytes, HTTP mailbox, persistent event/claim join, slot/budget execution and settlement. The stage neither reacquires the lock nor falls back to legacy work. Completion is separate from inventory sufficiency; UNKNOWN remains fenced.

ProcessBackend显式绑定精确原OriginalOwnerAuthority，operation须匹配当前owner/event/claim；run_tree的启动前、Windows恢复前、运行中与cleanup后复验authority。丢失authority走Job树清理并保留UNKNOWN。它是生命周期watchdog，不能称每次子进程业务写入都经过同步授权；固定worker/hash协议仍为isolated_offline。

The backend requires exact original authority and matching operation context, and supplies lifecycle checks around launch, Windows resume, execution and cleanup. Authority loss triggers tree cleanup and UNKNOWN. This lifecycle watchdog is not per-business-mutation synchronous authorization. The protocol remains isolated_offline.

## P1闭环 / P1 closure

先写job成功后释放的缺口：event分支暂存结果，release_run_lock在原BEGIN IMMEDIATE内复核owner、更新精确running/live/date原job，再释放锁，同事务提交。新固定额外要求锁UPDATE rowcount精确1；否则在事务退出前raise，job与锁一并rollback。

Terminal state is now deferred until original job finalization and lock release share the same immediate transaction. The lock update must affect exactly one row before transaction exit; otherwise both writes roll back.

独立重跑原精确故障探针：临时SQLite trigger仅对Inventory释放UPDATE执行RAISE(IGNORE)。实际stage抛RELEASE_UNVERIFIED，job从('running',None,None,None)完整保留原状，原owner仍held，backend调用1次。未再遗留completed/target_met。该trigger仅为隔离注入，不声称现场存在。

The independent zero-row failure probe now leaves the original running job unchanged and authority held while raising RELEASE_UNVERIFIED, with one backend invocation. No completed/target_met fact remains. The trigger is isolated test injection, not a site-schema claim.

## 独立验证 / Independent validation

固定源码76项全部通过，0failure/0error。原stage/owner/mutex/currentstage60项18.916秒，真实子进程backend及mailbox16项11.458秒；合计30.374秒为runner耗时之和，非总墙钟。真实原stage AST→HTTP→Windows Job child→预算→原job/锁同事务路径通过；原owner丢失的真实子进程测试验证UNKNOWN与cleanup。实际命令与文件/Gitblob SHA256见JSON，不继承dea9或旧687测试成绩。

All76 pinned-source tests passed. Summed runner durations were30.374 seconds. Tests include actual stage AST through HTTP, Windows Job child, budget settlement and atomic original finalization/release, plus live-owner loss and verified child cleanup. Exact commands and source hashes are in JSON. Earlier candidate results are not counted.

## 边界 / Scope limits

业务worker、签名与SAFE计数仍是夹具；未证明真实Provider、库存增长、完整受信命令/镜像句柄固定、真实Windows SCM/ACL或生产验收。受信wrapper和连接工厂为内部接口；没有生产配置、服务或调度器开启。未修改产品或生产DB、ACL、服务、Inventory、配置、凭据。正式后端与所有生产门禁保持false。

Business worker, signatures and SAFE counts remain fixtures. Formal Provider execution, actual inventory growth, complete trusted command/image pinning, actual SCM/ACL and production acceptance remain unproven. Trusted wrappers/factories are internal APIs. No product or production state was changed, and production gates remain false.

## 实际制品独立核验 / Independent actual artifact verification

同固定3fbaa源码工程包73payload全部hash通过：60原Gitblob字节相同、7host源码仅CRLF/LF等价、6明确生成观察。install74条文件、rollback18条文件与磁盘/BUILD/manifest逐字节一致；PE AMD64 0x8664。owner-companion17payload精确匹配固定Gitblob，manifest及ZIP摘要正确，expected_before只与3bbb固定Git基线比对，不是现场取证。ARTIFACT_MANIFEST记录115项实际制品均逐项验证。

All73 payload hashes passed, distinguishing60 exact Git blobs,7 newline-equivalent host sources and6 generated observations. Install/rollback archives contain74/18 files and match BUILD, disk and manifests byte-for-byte. PE is AMD64. The17 companion payloads exactly match pinned Git blobs;115 artifact-manifest records were verified. Baseline conditions refer only to3bbb Git bytes, not site evidence.

独立新临时目录解压，Python -I -B成功导入OriginalStageEvent、OriginalOwnerAuthority、ProcessBackend及OriginalOwnerSlotAdapter的新helper依赖闭包；未执行bd_db或原orchestrator顶层/main、不读配置/DB/凭据。17项并非原业务所有既有依赖的完整自包含发行包；无自动更新器或宿主白名单扩展。制品核验不是独立重现构建、完整可安装发布或生产批准，详情见INDEPENDENT_PACKAGE_RESULT.json。

Fresh isolated extraction and Python -I -B helper-closure import passed without bd_db/orchestrator top-level/main, configuration, DB or credentials. The17-file companion does not contain all legacy business dependencies and supplies no updater or allowlist expansion. Verification does not establish reproducible compilation, installability or production approval.
