# U1 安装源码与版本绑定 / Installer source and version binding

时间 / Updated: 2026-11-02T15:03:21.302808+00:00
固定源码 / Fixed source: `5c4002003cfdcbb1c1f0f6370b7c07e89823ba0e`
本轮恢复远端 / Remote at recovery: `7dfd82bcff3d56d48620bdeb1a50ff99ec316f7a`

中文：实际安装器新增必填独立 ApprovedSourceCommit，核对40位小写固定源码及 installer_version=1.1.0。首装、升级、恢复和完整回滚均经过同一准入检查；错误在生产写入前拒绝。安装清单、只读计划和新安装回执记录源码与版本。旧v2回执的既有归属校验保留。回滚工具命令已同步新参数。
English: The actual installer requires an independently approved source commit and checks its lowercase40-character value plus installer_version1.1.0. First installation, upgrades, recovery and full rollback share this admission gate before effects. Manifest, plan output and new receipts carry the source/version; existing v2 receipt ownership checks remain compatible. Rollback instructions include the new argument.

中文：23项定向测试通过（94.476秒），覆盖实际安装准入代码及隔离文件/安装协调器；不是生产安装验收。真实AMD64禁用安装包与回滚包已生成，65文件逐SHA256、ZIP完整字节和PE架构核验通过。新源码独立审核PENDING，不继承旧独审。
English:23 targeted tests passed in94.476 seconds, exercising actual admission code and isolated file/install coordinators, not production installation. Real AMD64 Disabled artifacts were built;65 file hashes, exact ZIP bytes and PE architecture passed. Independent review is PENDING for this source pin.

可比回归 / Fresh comparison: `{"baseline_commit": "7dfd82bcff3d56d48620bdeb1a50ff99ec316f7a", "candidate_commit": "5c4002003cfdcbb1c1f0f6370b7c07e89823ba0e", "isolated_root": "C:\\Users\\15690\\AppData\\Local\\Temp\\u1-compare-d974ldqo", "complete": true, "baseline_run": 833, "candidate_run": 833, "baseline_failures": 37, "candidate_failures": 37, "baseline_errors": 17, "candidate_errors": 17, "failure_ids_identical": true, "error_ids_identical": true, "all_green": false, "no_new_regression": true}`

安装包 / Install SHA256: `36680ea74fb9374d4fdb8f145ecca4bd0dc5985fdbad93788b384cae52883741`
回滚包 / Rollback SHA256: `0a6e912c344af343e14f3f02ffd14d257bec507d9310d6f4c21d987087d57c01`
外清单 / Outer manifest SHA256: `1b2428b8215dd30f57166f02f24228e4d12fb9522c4a1a2cd10d55c460491ad8`
宿主清单 / Host manifest SHA256: `1dc39e6b2162165f3ba79df6321f9b78bf058fbbd2203ce6bfb32b5b2334e4ba`

中文：正式维护排斥尚未完成。实际读取原executor/bridge后确认Inventory生产租约在原DB/owner内，不能将开发supervisor锁冒充正式维护权。没有调用inventory_acquire/release、没有改生产代码或DB。本轮闭合可直接实施的独立源码/版本绑定P0缺口；正式backend、原owner生产入口和维护排斥继续未完成。
English: Formal maintenance exclusion is unfinished. The existing executor/bridge keeps production Inventory authority in its original DB/owner; a development supervisor lock cannot substitute. No inventory acquire/release or production modifications were performed. This round closes the actionable source/version binding gap; maintenance, formal backend and production-owner configuration remain open.

中文：新消费证据固定WorkBuddy `10e269e814dbe7b7a4801fa99ca4cec11d5a67b2`，7份原始JSON完整保存并逐个重算Git blob SHA，解析通过。检查schema标识/嵌套schema、来源字段与时间；无独立JSON Schema，不宣称正式schema认证。operations缺少producer，保留NOT_RECORDED；producer payload摘要规范未提供，摘要仅保留为producer声明。实际采样22:47:34、22:52:59；报告22:53:12；Git提交22:53:26（均+08），独立保留。
English: Read all7 pinned WorkBuddy JSON files, retained exact bytes, recomputed Git blobs and parsed JSON. Schema markers/nested schemas, provenance and timestamps were inspected; no independent JSON Schema exists. Operations omits producer; payload-digest canonicalization is unspecified, so those hashes remain producer assertions. Sample, report and commit times remain distinct.

- CITY_STAGE_TRACE.json: `36d74f1be0c13fdb71ef1cef2e713ca60300658e`
- INVENTORY_SCHEDULER_RECONCILIATION.json: `a7d0280f02f94e5477cfc80b27c709d2533c6d88`
- PRODUCTION_RUNTIME_LATEST.json: `94df84ff99c654be169549fe29d706c8e7add46b`
- PROVIDER_REQUEST_AUDIT_24H.json: `7e67abe9ebf18cf1cc05dcd75a289ed1c00f349b`
- RELEASE_REGISTRY_SNAPSHOT.json: `514099a8157632b109adff18445cf8c02ac2b8b6`
- SAFE_AUTHORITY_SNAPSHOT.json: `5a9f79681d3f07136b4a37c620b6403ccbe748d8`
- WORKBUDDY_LONG_TERM_OPERATIONS.json: `09fc4a48fcb48ca2321d992eb406e1f51ce703f6`

中文：SAFE两次69/69；producer称24h+1、7d+9，但同一文件reason/unavailable仍称没有同口径基线，因此严格净增长UNKNOWN。Inventory7个firing中6个可在runtime对到inventory stage，另一个误配post-send；runtime实际还有该窗口inventory:2026-11-01:784b352d，不能静默替换producer配对。一次漂移744.6秒超过声明600秒容差，零漏跑结论需对账。下一计划2026-11-03 01:55:58.202+08。最新多个run包含16条真实stage事件，但旧field_notes仍否认事件，保留矛盾，不把旧NOT_RECORDED覆盖原始事件。
English: SAFE readings agree69/69. Numeric growth+1/+9 contradicts the same file's missing-baseline reason/unavailable fields; strict growth remainsUNKNOWN. Six of7 firing pairs map to Inventory stages; one incorrectly points to post-send although runtime also contains inventory:2026-11-01:784b352d. Preserve both instead of silently repairing producer evidence. One744.6-second drift exceeds600-second tolerance; zero-miss acceptance needs reconciliation. Next firing is01:55:58.202+08. Actual16-event stage traces coexist with stale denial notes.

中文：Cooperstown正式关闭；operations下一动作仍说不会关闭，属于残留矛盾。Lake Placid20/20但web pending、completed_at=null，不能报正式关闭；本批无Ithaca，旧冲突未解除。Provider城市22过去24h零请求；全城市7d39请求39成功，仅该范围。8791 UP_SESSION_SCOPED不等于无人登录持久运行；启动持久性未通过，7877真实注销/重启出口UNKNOWN。producer称SMTP=false、未授权邮件0、sendlog今日0；本轮仅Git/离线临时测试，无生产DB/账本/配置写入或手动采集。
English: Cooperstown is closed, contradicting stale next-action prose. Lake Placid20/20 remains web-pending with null completion; Ithaca is absent and its earlier conflict remains. Provider scope: city22 has zero requests in24h; all cities have39 successful requests in7d. Session-scoped8791 health does not prove unattended persistence; boot persistence remains unaccepted and actual7877 logoff/reboot egressUNKNOWN. SMTP is off, unauthorized mail0 and today's sendlog0 per producer. This round performed only Git/offline operations.

消费回执 / Consumption receipt: PENDING_PUBLICATION (update only after Issue2 readback).
下一动作 / Next: 在现有安装器实现与唯一原 Inventory owner 共享的正式维护排斥准入，保持安装门禁关闭；随后完成正式 backend 接入。
Implement installer maintenance admission shared with the sole existing Inventory owner, keeping installation gated; then complete the formal backend integration.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false. 唯一原Inventory / Sole original Inventory:1784775229336.
未安装/启用生产服务，无第二调度器。No production installation/start or second scheduler.
