# U1 原所有者会话接线交付 / Original-owner session integration delivery

固定源码 / Fixed source: `68788653c848659c63f85021075fedee4aca5b13` | 2026-11-03T13:07:12.844134+00:00

## 实际工程 / Implemented engineering

中文：原bd_db取锁事务现在同时持久化PID创建身份、随机nonce及原数据库路径/文件身份。原stage捕获取锁事务返回的会话凭据，释放必须同事务匹配该凭据；旧finally、同holder重用及死进程不能释放新会话。服务host可用受信只读原DB连接工厂观察原owner，HTTP不接收DB路径、PID或权利来源。OriginalOwnerSlotAdapter复用原slot、预算与签名验证，不创建supervisor锁或新调度器。

English: The original bd_db acquisition transaction now persists process creation identity, random nonce and original-database path/file identity. The original stage captures the transaction's capability; release matches that capability in the same transaction, preventing stale finally blocks, reused holders and dead processes from releasing a new incarnation. The host can observe the original owner through a trusted read-only DB connection factory; HTTP accepts no DB path, PID or authority source. OriginalOwnerSlotAdapter retains existing slot, budget and signature checks without creating a supervisor lock or scheduler.

中文：原DB事件intent在HTTP之前落盘，回包丢失不得换事件重试；预算和slot claim之后、backend之前持久化精确claim关联。operation及两种受信收据均绑定当前owner、事件和claim摘要。结算失败保持树unverified和原锁，禁止新日期执行与安装维护取权。取消日志拒绝占用三个受保护数据库及其SQLite保留侧文件。全部动作仅在开发源码、临时数据库及隔离回环测试完成。

English: Original-DB event intent precedes HTTP; a lost response cannot authorize another event. After budget/slot claim and before backend invocation, the exact claim join is persisted. Operations and both authenticated receipts bind the current owner, event and claim digests. Failed settlement retains an unverified tree and original lock, blocking a new business date and installation maintenance. Cancellation journals cannot occupy protected databases or SQLite sidecars. All actions used development source, temporary databases and isolated loopback tests.

## 测试及独审 / Tests and independent review

- 当前固定组合 / Current fixed-candidate combined suite: 257 PASS, 289.573s; failures=0, errors=0, skips=0.
- 独立范围审核 / Independent scoped review: OFFLINE_SCOPED_REVIEW_PASSED; 119 PASS, 31.647s. 两P1及侧文件缺口已修复；修复前诊断原样保留。 / Both P1 findings and the sidecar gap were repaired; pre-fix diagnostics are retained.
- 额外探针 / Additional probes: claim关联提交前后丢ACK均0 backend调用、禁止释放及重放；真实进程os._exit(29)保留封锁；20轮事件intent/释放竞争没有双成功。独审记录20次均释放先赢，不声称随机探针覆盖两种调度顺序。 / Lost ACK before/after claim-join commit yields zero backend calls and denies release/replay; actual os._exit(29) preserves exclusion; 20 intent/release races had no dual success. The independent report records release winning all 20 runs, without claiming both scheduling orders were randomly observed.
- 可比全量 / Comparable full regression: baseline `4b0353cbc4a5c69998fdd597d2bb884f7f5da8d0` / candidate `68788653c848659c63f85021075fedee4aca5b13`: 833 / 833 tests; failures 37 / 37; errors 17 / 17. NO_NEW_REGRESSION=True; ALL_GREEN=False。未继承旧SHA结果，不宣称全绿。 / Old-SHA results are not inherited; no all-green claim.

## 制品 / Artifacts

真实AMD64宿主已重新编译，72载荷文件；另附八文件原所有者依赖包，fresh Python -I仅导入验证通过。每个文件摘要见ARTIFACT_MANIFEST.json；独立制品审核见review-6878865。外部CPython未捆绑。原Publisher源码未改变，本轮不将旧Publisher包冒充新SHA包。

The actual AMD64 host was rebuilt with 72 payload files. The separate eight-file original-owner dependency archive passed a fresh Python -I import-only check. ARTIFACT_MANIFEST.json records every file digest; see review-6878865 for independent artifact checks. External CPython is not bundled. Publisher source is unchanged; an old Publisher archive is not relabeled as this candidate.

- install.zip SHA256: `e55905083281bcafcfa11b939b150d1b2c57ddd31f0fb7850372621b349f8732`
- rollback-tools.zip SHA256: `41b85581731be508b863bfa2ae390f4a3cfe7efca7cd8e0bd5f37f284554d443`
- Host manifest SHA256: `7fd387a3fe0f140d8212eb61af0bf53d8fa66803286730b1044586924bedbfa7`
- owner-companion.zip SHA256: `abc3d0d2903b06e48e429e48ca8c5affea6dd05b66f79d63a3551e8886de0725`
- Owner manifest SHA256: `72943a2576382eba2ccbe6eb075c634068fd354c919ab76e05def71bd6ef8e65`

## 尚未完成及现场门禁 / Remaining work and site gates

完成正式Provider/backend协议与原stage入口、服务事件消费者的固定调用链；保留原唯一Inventory、持久事件/claim/费用/取消和结算合同。当前原owner身份适配器仍使用isolated_offline协议，不是正式Provider接线完成。完整候选审核和授权后再做隔离Windows首装、升级、中断恢复及回滚验收。

Complete the fixed call chain connecting the formal Provider/backend protocol, original stage entry and service event consumer, retaining the sole original Inventory and durable event/claim/cost/cancellation/settlement contracts. The current original-owner adapter still uses the isolated_offline protocol and does not complete formal Provider wiring. After complete-candidate review and authorization, perform isolated Windows first-install, upgrade, interruption recovery and rollback acceptance.

中文：原stage目前仅接入会话捕获与释放核验，尚未改成正式服务事件调用入口；实际HTTP端到端测试由隔离现有owner进程消费，业务backend/费用收据为受信测试替身。不能将该测试当真实Provider执行或完整可安装版本。真实PowerShell/SCM/ACL成功路径、Windows首装/升级/安装与回滚中断及无人值守周期仍需完整候选和授权后验收；不重复索要WorkBuddy已交P1证据，不绕过执行策略。

English: The original stage currently captures and validates the owner capability at release; it is not yet the formal service-event entry. Actual HTTP end-to-end tests consume from an isolated existing-owner process, with business backend/cost receipts supplied by trusted test doubles. This does not prove real Provider execution or a complete installable release. Successful real PowerShell/SCM/ACL paths, Windows first install/upgrade/install and rollback interruption, and unattended cycles still require a complete candidate and authorization. Existing WorkBuddy P1 evidence is reused; execution policy is not bypassed.

中文：WorkBuddy下一步只需针对最终完整SHA核验Disabled/Stopped、非对称ACL、精确文件所有权、维护权持续持有、故障恢复以及唯一Inventory排他；当前不要求安装或现场写入。

English: WorkBuddy should later verify Disabled/Stopped state, asymmetric ACLs, exact file ownership, continuous maintenance authority, fault recovery and sole-Inventory exclusion against the final complete SHA. No installation or site writes are requested now.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`
