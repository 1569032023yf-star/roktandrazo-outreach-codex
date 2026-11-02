# U1 维护准入缺口与执行请求修复 / Maintenance admission and request integrity

时间 / Updated: 2026-11-02T18:03:22.176387+00:00
恢复远端 / Remote at recovery: `fe1ec08a3c6a392f81305c2f732992a6e352c3f0`
固定源码 / Source: `a20ba1e67b0633e8a588ec90db981b9a99d3a3fa`; installer_version=1.1.1.

中文：核对真实安装调用链发现，公开 Execute 入口此前仅持有安装器自身互斥，仍可在没有原 Inventory 实时维护排斥时写入。现已在所有公开首装、升级、恢复、完整回滚以及旧撤注册入口，于目标访问/日志创建前硬拒绝。没有新增解锁参数、没有将开发 supervisor 锁冒充生产权威；manifest 和 DELIVERY 明示 allow_install=false、formal_maintenance_integrated=false。这是关闭不安全准入缺口，正式维护适配器仍未实现，当前版本不能正式安装。
English: The actual public Execute entrypoints previously held only the installer mutex, allowing effects without exclusion coordinated with the original Inventory. Installation, upgrade, recovery, full rollback and legacy deregistration now reject before target access/journal creation. No bypass switch or substitute development lock was added. Manifest and DELIVERY explicitly declare installation disabled and maintenance integration absent. This closes unsafe admission; it does not complete the maintenance adapter or make this pin installable.

中文：实际 HTTP 事件接线此前只对响应拒绝重复JSON字段，接收请求仍可最后值覆盖。现在在任何持久事件预留/回报前，拒绝顶层与嵌套重复字段和非有限常量；实际回环端口验证拒绝请求后事件表仍为0，执行器未启动。沿用原租约、持久slot、预算与取消日志，UNKNOWN不重放，无新调度器。
English: The real event HTTP path previously rejected ambiguous replies but still accepted duplicate request keys. It now rejects top-level/nested duplicate keys and non-finite constants before durable event reservation/reporting. Loopback tests prove rejected requests leave zero event rows and never enter the executor. Existing lease/slot/budget/cancellation paths remain authoritative; UNKNOWN never replays.

中文：29项定向测试通过，测试运行器104.669秒（外层105.110秒）；包内实际模块导入7项通过（运行器4.849秒，外层5.201秒）。初次夹具直接调用脚本被现有系统执行策略拒绝；已改为执行完整同源码的EncodedCommand，未改变系统策略，然后完整定向重跑通过。65文件逐SHA256、两份ZIP精确字节及AMD64 PE验证通过。新固定源码独审PENDING，旧候选审核不继承。
English:29 targeted tests passed;7 tests importing the actual package modules passed. The initial harness hit the existing execution policy; executing the exact full source through EncodedCommand fixed the harness without changing system policy, followed by a complete passing targeted rerun. All65 file hashes, both archives and AMD64 PE verified. Independent review is PENDING for this source pin.

新可比回归 / Fresh comparison: `{"baseline_commit": "fe1ec08a3c6a392f81305c2f732992a6e352c3f0", "candidate_commit": "a20ba1e67b0633e8a588ec90db981b9a99d3a3fa", "isolated_root": "C:\\Users\\15690\\AppData\\Local\\Temp\\u1-compare-e2nhhobv", "complete": true, "baseline_run": 833, "candidate_run": 833, "baseline_failures": 37, "candidate_failures": 37, "baseline_errors": 17, "candidate_errors": 17, "failure_ids_identical": true, "error_ids_identical": true, "all_green": false, "no_new_regression": true}`
安装包 / Install SHA256: `185d08c02cdef3e334d4b0fa0d6bf4b90f77b6ce89fb506fec1c31b69957bf0e`
回滚工具包 / Rollback SHA256: `2c676e3f1402b678e9cc6fdb957d4c339a9cce932d42f67cd2395182d5406584`
外清单 / Outer manifest SHA256: `a26c14bb8a39f5f8b25f1a34533e4cd7da43de55032cc1412ec6ea7e7c75eb01`
宿主清单 / Host manifest SHA256: `03f0497713e6908f7b9fd10acd82c5fc09c9a6580d00ccab07cc43b4d97e6b2b`

中文：实际重读Issue2/6567493676 A、本地canonical、checkpoint和工程规范；远端与本地起始均fe1ec08，tracked clean，无并行U1任务，旧recovery guard保留。WorkBuddy main仍为10e269，复用已核验回执6580465343，不重发消费回执或合同请求，不重采生产证据。SAFE69与严格增长UNKNOWN、Inventory配对矛盾、会话8791及7877无人登录UNKNOWN沿用已记录范围，不推导新验收。既有自动化3小时规则未改；未发现硬超时字段，45分钟是本轮预算，不宣称平台强制终止。
English: Re-read the directive, actual canonical/checkpoint and repository rules. Local/remote recovery heads matched fe1ec08 with no tracked changes or concurrent U1 task; the existing recovery guard was preserved. WorkBuddy main remains10e269, so reuse verified receipt6580465343 without duplicate consumption/contracts or production sampling. Existing SAFE/growth/scheduler/session/egress conclusions remain scoped. The3-hour automation is unchanged; no hard-timeout field was found, so45 minutes is a run budget rather than a claimed platform kill limit.

下一唯一动作 / Next: 在离线源码中实现原生产 Inventory 权威持有的维护排斥适配器，再将安装入口接入整个写入与核验期间持续持有的排斥；不能把本轮硬拒绝当作维护集成完成。
Implement the original production Inventory authority maintenance adapter in offline source, then hold exclusion throughout installer mutation and verification; hard rejection alone is not completed maintenance integration.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false. 唯一原Inventory / Sole original Inventory:1784775229336.
本轮无生产DB/账本/服务/ACL/调度/配额/SMTP变更，无手动采集。No production DB, ledger, service, ACL, scheduling, quota, mail changes or manual collection.
