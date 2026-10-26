# U1 A 持久槽位实现 / Durable Slot Implementation

基线 / Baseline: b3a0d3ae26ef99fea5f458ec029301d233a27f7c（编辑前 ls-remote 已核对 / verified before edits）

中文：新增 autonomy/durable_slots.py 真正持久 SQLite 协议，不是测试 helper。固定 Inventory 1784775229336，七状态；BEGIN IMMEDIATE 与 FULL synchronous 事务；唯一 slot/due；原子 claim、一次 start、UNKNOWN、可信终态对账、单调 authority epoch 及事务审计。pending 可被新的可信最新槽延期，claimed/running/unknown 不会超时重放，并阻止所有新 claim 和切换权威；completed/failed 不重派。回滚到旧 owner 必须取得新 epoch 且已排空，不能倒退 epoch。

English: autonomy/durable_slots.py is a real persistent SQLite protocol, not a test helper. It fixes Inventory 1784775229336, supports seven states, BEGIN IMMEDIATE/FULL synchronous transactions, unique slot/due keys, atomic claim, one-time start, UNKNOWN, authenticated terminal reconciliation, monotonic authority epochs and transactional audit. New authenticated latest slots defer pending work; claimed/running/unknown never time out into replay and block all new claims and authority switches. Completed/failed slots never replay. Restoring an old owner requires a new epoch and drained work.

中文：证据验证默认拒绝。verify(envelope) 必须返回经外部可信认证的 payload，不能返回布尔授权；本模块只读取其返回值并校验身份、时间窗、kind、slot/epoch/owner 与严格布尔绑定。与B的 EvidenceConsumer 接入需在验签后映射 inventory_id/observed_at_epoch/expires_at_epoch 至 inventory/observed/expires。测试使用明确标记的合成验证器，不冒充生产验签。完整完全相同回执幂等；同终态但不同回执摘要拒绝，需人工/可信对账而非猜测同义。

English: Evidence verification denies by default. verify(envelope) must return externally authenticated payload, not boolean authority. Only that payload is read and checked for identity, validity window, kind, slot/epoch/owner and strict boolean bindings. B EvidenceConsumer integration requires post-verification mapping of inventory_id/observed_at_epoch/expires_at_epoch to inventory/observed/expires. Tests use an explicitly synthetic verifier, not production authentication. Exact identical receipts are idempotent; different digests for the same terminal state fail closed instead of assuming equivalence.

中文：admit_due 只接受可信 next_due 和 latest_due，不计算 cron。遗漏槽清单最多100项，只作为 deferred 与最新 pending 同事务记录，不派发追赶。合成 fixture 重建18.2小时空档、6/12小时两漏槽、18小时最新槽，并验证完成跨日后用显式 completion+6h 的111600秒，不对齐整点。该fixture解释语义，不是声称取得完整生产 firing 历史。

English: admit_due accepts only trusted next_due/latest_due, never computes cron. At most 100 missed slots are recorded as deferred in the same transaction as the latest pending slot; no catch-up dispatch occurs. A synthetic fixture reconstructs an 18.2-hour gap, missed 6/12-hour slots and latest 18-hour slot, then explicit completion+6h at 111600 seconds across a date boundary. It validates semantics, not possession of full production firing history.

中文：最终12项模块测试与既有13项联合共25项通过（1.644秒）。包括两个spawn进程竞争、实际 os._exit 在claim前/提交前/提交后、合成外部副作用后回执丢失退出、连接重开、只读SQLite、提交前磁盘异常注入和提交后回执异常、重复失败回执、UNKNOWN、epoch及可信证据冲突。早期4进程竞争已通过；宿主低内存后限制为2。首轮发现snapshot上下文不关闭连接，已显式closing修复并复测通过。物理磁盘满/断电/OS重启未执行。

English: All 12 module tests plus 13 existing tests passed (25 total, 1.644 seconds), covering two spawn-process contenders, actual os._exit before claim/before commit/after commit, exit after synthetic external effect without receipt, database reopening, read-only SQLite, injected precommit disk errors/postcommit acknowledgement errors, duplicate failed receipts, UNKNOWN, epochs and authenticated-evidence conflicts. An earlier four-process trial passed; low host memory subsequently reduced concurrency to two. Initial snapshot connection leakage was fixed with explicit closing and retested. Physical disk-full, power-loss and OS reboot were not tested.

中文：复用既有 lock_recovery.exclusive_lock 的隔离组合测试通过；本协议不替代正式运行锁，未来调用者必须持续持锁覆盖准入与外部副作用。start 返回 RUNNING_NOT_DISPATCHED，不启动Provider。账本与外部系统不能提供跨系统原子提交；丢回执后牺牲可用性保持不重放。真实权限/密码证据、外部锁权威互斥、状态导入、预算原子集成和生产通道仍待集成审核，旧执行器若不遵循epoch不能仅凭此库被物理阻止。新增文件不绕过正式发布器限制。

English: Isolated composition with existing lock_recovery.exclusive_lock passed. This protocol does not replace the formal run lock; integrators must hold it across admission and external effects. start returns RUNNING_NOT_DISPATCHED and starts no Provider. Cross-system atomic commit is unavailable; lost receipts deliberately sacrifice availability to prevent replay. Real authority/authentication, external-lock exclusion, state import, atomic budget integration and production channels await integration review. Legacy executors ignoring epochs are not physically fenced by this library alone. New files must not bypass publisher limitations.

中文：实现者自检，独立审核PENDING；RELEASE_READY=false，PRODUCTION_DEPLOYED=false。生产数据库/SMTP/采集均零操作。预算持久化属于D，尚不能说整体U1开发完成。下一步独立固定差异审核、B认证适配与D预算事务集成。双语、秘密、范围、数量、未执行与风险自检通过。

English: Implementer self-check only; independent review is PENDING, RELEASE_READY=false, PRODUCTION_DEPLOYED=false. No production database, SMTP or collection actions occurred. Durable budgets belong to D; overall U1 development is not complete. Next: independently review pinned changes and integrate B authentication and D budget transactions. Bilingual, secret, scope, count, unperformed-work and risk checks passed.
