回滚工具 / Rollback tools

文件发布指针：release_store.py --root STORE rollback TRANSACTION --expected-current VERSION。
File publication pointer: use that command with retained versions/backups.

禁用宿主完整文件/注册回滚：从host/调用 Install-DisabledHost.ps1 -Rollback -PackageRoot HOST -ApprovedManifestSha256 HASH -ApprovedSourceCommit SOURCE_SHA -RuntimePlan PLAN -ApprovedRuntimePlanSha256 PLAN_HASH -Execute。未决操作使用-RecoverInstall；两者仅补偿已知状态，禁止自动重放。
Disabled-host file/registration compensation: use the above exact manifest and runtime plan. Use -RecoverInstall for interrupted operations; neither action replays forward effects.

旧Rollback-DisabledHost.ps1只撤销注册，不是完整文件回滚。保留管理员审计目录全部日志；升级保留原有状态；首次安装回滚只清理身份匹配的事务新建空根。新部署还需要正式维护租约与身份门禁。此包不是数据库或现场状态备份。
The legacy Rollback-DisabledHost.ps1 is registration-only. Retain all administrator audit journals; upgrades preserve existing state, while fresh rollback removes only recorded empty roots with matching identities. Formal maintenance/identity gates remain required before installation. This archive is not a database/site-state backup.
