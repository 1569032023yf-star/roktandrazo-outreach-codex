# 工作树诊断独审 / Working-tree diagnostic independent review

结论 BLOCKED_WORKINGTREE_DIAGNOSTIC。22项隔离测试通过（3.119秒），但三项附加探针揭示边界缺口，不能用既有测试通过抵销。父代理已确认前两项并正在修复；本报告只记录修复前诊断，不代表后续固定候选。

Status: blocked diagnostic. All 22 isolated tests passed in 3.119 seconds, but additional probes exposed the following gaps. The main agent accepted the first two and is implementing fixes. This is not a review of the future fixed candidate.

1. P1：旧原owner释放后同进程/日期/holder再次获得新nonce，旧式实际 bd_db.release_run_lock 仍返回True。release只检查当前session，没有检查调用者捕获的binding。必须传入旧调用者实际持有的expected binding，事务内比较，缺失拒绝。

   P1: The actual release API accepted a stale caller after a new nonce was acquired with the same process/date/holder. It validated the current session instead of the caller's captured incarnation. Require an explicit captured binding and compare inside the transaction.

2. P1：旧事件完成后获得新owner、新admission并prepare新事件，用旧slot/budget收据直接reconcile，返回COMPLETED和两种duplicate，设置新tree=verified_closed并准许释放。operation加入event摘要但收据、持久预算claim及reconcile未join该owner/event。需要持久原owner→event→claim关联并要求受信收据绑定同一关联。

   P1: Prior receipts closed a newly prepared event under a fresh owner and enabled release without a new backend call. Operation metadata alone did not bind settlement. Persist the owner/event/claim join and require authenticated receipts to match it.

3. P2：取消journal路径检查接受原数据库-journal/-wal/-shm保留路径。探针仅检查路径，未写这些文件。配置来自受信内部而非HTTP，但误配可占用原SQLite事务侧文件名；需保护main及侧文件路径与实际别名。

   P2: Cancellation-journal validation accepted reserved SQLite sidecar names. The probe only checked paths and did not write them. Trusted internal configuration is still susceptible to accidental sidecar collisions; protect both reserved names and existing aliases.

只做临时SQLite和替身backend验证。未修改产品、生产DB、服务、ACL或Inventory。formal backend与生产门禁保持false；实际provider接线尚未完成。源码工作树哈希写于JSON，因并行开发继续变化，本记录为诊断采样，不作为固定源码验收。

Only isolated SQLite and backend doubles were used. No product or production state changed. Formal backend and production gates remain false. File hashes describe a diagnostic working-tree sample, not a frozen release candidate.
