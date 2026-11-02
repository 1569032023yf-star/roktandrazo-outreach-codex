# 安装配置集成 / Installer configuration integration

更新时间 / Updated: 2026-11-02T06:58:13.090340+00:00
固定源码 / Fixed source: a5751e8e67ceeac6e9568571ecf7c69c074ec952

已按 Issue2 评论6567493676 修改真实安装器：从独立批准哈希的配置计划自动生成 runtime.json 与 supervisor.json；绑定Python、bootstrap、配置哈希，拒绝过期认证、路径与输入漂移；CreateNew及逐字节回读，执行安装缺计划拒绝。没有执行安装。
The real installer now generates runtime.json and supervisor.json from a separately hash-approved reference plan. It binds Python/bootstrap/config hashes, rejects expired credentials and path/input drift, uses CreateNew and byte readback, and refuses execution without a plan. Installation was not executed.

组合测试37项通过，11.385秒。先前测试因Windows PowerShell环境缺命令失败，改为当前pwsh运行；UTF8读回修复后组合通过。测试只隔离执行配置生成块，未验证真实管理员安装、ACL或服务启动。
37 combined tests passed in11.385s. Initial Windows PowerShell environment lacked the command; current pwsh and UTF8 capture pass. Provisioning tests execute the actual configuration-generation block in isolation, not administrator installation, ACL or service startup.

安装包 / Install zip SHA256: 36616471b9f09707649c34e5335c1c18f19d7d326af88d3ecf29740bc88b3a03
回滚工具包 / Rollback tools SHA256: 9672e93d1b19f4040bfaf5871d44f7131b825a6319a3898c83a7a6665c9d9216
清单 / Manifest SHA256: a205e30534780af9c8ca2169e25ea91656015a9e6d7636408df62188e7677deb
回滚工具不是现场完整备份。独审PENDING，生产安装未执行。发布器目标身份、reparse/hardlink/TOCTOU、升级和完整回滚尚未闭环；本次哈希检查不构成并发替换防护。正式backend与原Inventory准入尚未接通，不把只读8791服务称为自动执行。
Rollback tools are not a complete site backup. Independent review PENDING; no production installation. Publisher target identity, reparse/hardlink/TOCTOU, upgrade and full rollback remain open; hash checking does not establish race protection. Formal backend/original Inventory admission is not integrated; readonly8791 is not automatic execution.

原自动任务rokt-razo已更新，仍每3小时，Prompt限制45分钟和最多两条重线；平台未提供硬超时字段。Prompt SHA256: 0e61d66affd96889ba921a73e60aa23180ade5d37d78f7797b8dd24e34aeaf42
Existing automation rokt-razo was updated, retaining3-hour cadence, a45-minute prompt budget and at most2 heavy workstreams. No platform hard-timeout field was provided.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN

下一动作 / Next action: Integrate bounded execution backend with existing signed SingleSlotAdapter admission and original Inventory lease; close installer upgrade/rollback, dependency ACL and TOCTOU blockers before independent review. No service install/start.
