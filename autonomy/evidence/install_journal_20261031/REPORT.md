# 安装意图日志初版 / Installation intent journal primitive

中文：固定源码 `deecc456b97736d6f895879ee1c0b086a8f84e34`。实现 CREATE_NEW 独占操作日志，每条意图及回执写入后 fsync；写入/flush失败使当前writer不可再用。恢复只读、不重新打开writer、不截断、不重放。同operation_id拒绝覆盖。顺序拆分代码ACL和状态ACL，第二次ACL意图后真实子进程exit17，恢复保留4项已记录回执和STATE_ACL未决状态。日志损坏或截断返回UNKNOWN；全部回执仅代表记录齐全，不证明真实系统副作用或验收。

English: Pinned source `deecc456b97736d6f895879ee1c0b086a8f84e34` implements a CREATE_NEW exclusive operation log with fsync after each intent/receipt. Write/flush failure poisons the writer. Recovery is read-only, never truncates, reopens a writer or replays effects. Duplicate operation IDs cannot overwrite. Separate code/state ACL steps preserve four receipts and pending STATE_ACL after an actual child exits17. Invalid/torn logs are UNKNOWN; complete receipts establish recording only, not OS effects or acceptance.

中文：41项组合测试通过（2.920秒），含4项新测试：真实进程突然退出、顺序与重复意图拒绝、flush失败、损坏日志；组合覆盖安装设计/包、HTTP、恢复状态及Inventory归因。git diff --check通过。独立审核PENDING，不继承旧833项全量结果；未做新全量回归。

English: 41 combined tests passed in2.920s, including four new tests for process exit, order/duplicate intents, flush failure and corrupted logs, alongside installation plan/package, HTTP, recovery status and Inventory attribution. Diff whitespace check passes. Independent review remains PENDING; old833 results are not inherited and no new full regression was run.

中文：限制：调用者必须提供已受保护审计目录；本组件不建立或验证Windows ACL，不验证维护租约真实性，不保证掉电时目录项持久性，不是防篡改日志。尚未接PowerShell或真实OS适配层，不能安装。未改生产代码、DB、SMTP、调度、服务、ACL或代理。缺失CURRENT_STATUS.md/FILE_MANIFEST.md已记录；不影响本轮隔离离线开发。WB远端仍74140982，沿用已核验回执6535746968不重复发。

English: Limitations: caller supplies an already protected audit directory; this component neither establishes/verifies Windows ACLs nor authenticates a maintenance lease, guarantees directory-entry durability on power loss, or provides tamper resistance. No PowerShell/real OS-adapter integration; not installable. No production code/database/SMTP/scheduler/service/ACL/proxy mutation. Missing CURRENT_STATUS.md/FILE_MANIFEST.md recorded; isolated offline development only. WB remote remains74140982; existing verified receipt6535746968 is retained without reposting.

中文：下一步：固定源码独审；可注入OS适配层故障合同、受保护目录验证、日志与实际副作用绑定、原子首次发布及正式维护租约；未决副作用只status。DEVELOPMENT_COMPLETE=false；RELEASE_READY=false；PRODUCTION_DEPLOYED=false；PRODUCTION_ACCEPTED=false；BUSINESS_GROWTH=UNKNOWN。

English: Next: independent pinned-source review; injectable OS-adapter fault contracts, protected-root validation, binding records to actual effects, atomic first publication and formal maintenance lease. Unresolved effects permit status only. All four overall development/release/deployment/acceptance flags remain false; business growth UNKNOWN.
