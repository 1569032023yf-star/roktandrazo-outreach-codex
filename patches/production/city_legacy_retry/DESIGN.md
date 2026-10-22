# 城市旧恢复账本兼容候选 / City legacy recovery ledger candidate

中文：这是隔离开发候选，未 push、注册、发布或操作生产。只发布 discovery/discovery_service.py 与 retail_city_queue.py 两文件；baseline 是经 SHA 核对的正式生产源码，不复制开发工作树。生产556/565原始账本未获补证，不能声称精确重现其生产根因，历史阶段仍 NOT_RECORDED。

English: This isolated development candidate has not been pushed, registered, deployed or run against production. The only release targets are discovery/discovery_service.py and retail_city_queue.py; the baseline matches the production SHA and the development checkout is not a deployment bundle. Raw production ledgers for 556/565 remain unavailable; this is a structural compatibility reproduction, not their proven exact production root cause. Historical stages remain NOT_RECORDED.

中文：完整真实失败事件优先。计数不兼容但完整事件合法时仅按原事件数量修复计数（20次总尝试/1次真实失败不会变成20次网络失败），继续原1800秒跨天门禁；三次完整且间隔合法的真实失败才可网络耗尽。无完整兼容事件的非空旧账本，按用户人工复核隔离授权原样归档，存版本、UTC时间、SHA256、原结构及独立 legacy_metadata_manual_review 分类。此分类不表示无邮箱、不生成失败事件、不改变leads或SAFE。单周期迁移数量受原max_results限制；过大账本保守保留。新schema2纯程序异常记账不误当旧网络失败。每次写入使用savepoint，不commit调用者事务，失败回滚。

English: Complete real failure events take precedence. A malformed count with otherwise valid unchanged events is normalized from those events only: 20 total attempts with one real failure remains one failure. The existing 1800-second and cross-day due gate remains. Only three complete, spaced real failures can exhaust the network budget. A nonempty incompatible legacy ledger is archived intact under the user's explicit manual-review isolation authorization, with version, UTC timestamp, SHA256, original structure and a separate legacy_metadata_manual_review classification. This is not no-email, does not invent failures, and changes neither leads nor SAFE. Migration writes are bounded by the existing max_results; oversized ledgers remain open. Schema2 program-error bookkeeping is not a legacy network failure. Savepoints preserve caller transaction ownership and rollback on errors.

中文：关联候选先走原身份、地区、组织、历史和资格门禁，再允许兼容迁移。provider重复不能注入恢复键，旧归档保留。城市只把完整版本化人工分类作为已交人工工作；无效/被改动元数据不收尾。原矩阵、候选资格及下一城市激活条件不放宽。回滚为manifest中精确baseline，change.patch经git apply正反校验及逐字节比较。

English: Linked candidates must pass the original identity, location, organization, history and qualification gates before compatibility migration. Repeated provider hits cannot inject recovery keys and preserve archived ledgers. The city treats only a fully validated versioned classification as work handed to manual review; invalid or altered metadata cannot close it. The matrix, qualification and next-city activation conditions are not loosened. Rollback uses the exact manifest baseline; change.patch passed forward/reverse git apply checks and byte comparisons.

中文：23项离线定向测试通过，覆盖原网络恢复、跨天、provider重复、程序错/transport分类、事务、三次失败、城市矩阵/下一城、新20/1与31缺失及幂等人工隔离。生产精确基线对旧第三次成功fixture会进入identity_review，候选同样拒绝，测试明确保留该行为；不能为旧fixture放宽身份。局限：本地测试不证明正式bridge读取或自然Inventory验收；必须独审、正式发布门禁和原计划自然验收。

English: All 23 targeted offline tests passed, covering existing recovery, cross-day scheduling, duplicate providers, program errors/transport classification, transactions, three failures, city matrix/next city, new 20/1 and missing-history31 cases and idempotent manual isolation. The exact production baseline rejects the old third-success fixture into identity_review and the candidate preserves that rejection; the test explicitly preserves this gate. Local tests do not establish bridge consumption or natural Inventory acceptance; independent review, formal release gates and natural acceptance on the original schedule remain required.

中文：独审P2已修复：staging_ids在任何兼容迁移前收窄；空列表无写入，单ID不迁移其他行。
English: Review P2 fixed: staging_ids restricts rows before any compatibility migration; an empty list writes nothing and a single ID cannot migrate other rows.
