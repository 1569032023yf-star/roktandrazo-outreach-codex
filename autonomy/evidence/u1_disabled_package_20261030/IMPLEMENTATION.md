# U1 禁用宿主开发包 / Disabled host development package

## 实际结果 / Actual results

INSTALLER_IMPLEMENTED=true
REAL_DEV_PACKAGE_BUILT=true
PRODUCTION_INSTALLABLE=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false

已实现真实 PowerShell 安装及登记回滚脚本、严格输入与精确字节校验构建器，并用系统 .NET Framework x64 编译出真实 7680 字节 PE。安装脚本默认仅预检；只有显式 Execute 且管理员身份、精确批准清单哈希及环境检查通过后才登记禁用服务，绝不启动。所有生产副作用均未执行。
Executable PowerShell installation and registration rollback scripts, strict staging validation, and a real 7680-byte x64 .NET Framework PE are implemented. Installation defaults to preflight. Explicit Execute, administrator identity, exact approved manifest hash and environment checks are required for disabled registration; no service is started. No production mutation was performed.

这是 SCM 本地 heartbeat 宿主，不提供 8791 listener、WorkBuddy 桥接、正式 backend、生产 scheduler 或 Python/SQLite 执行。它不采集、不联网、不派发或取消 Inventory、不发邮件。不能替代正式无人登录业务执行闭环。
This SCM local-heartbeat host has no 8791 listener, WorkBuddy bridge, formal backend, production scheduler, or Python/SQLite execution. It performs no collection, networking, Inventory dispatch/cancellation, or email. It does not establish unattended business execution.

## 包与验证 / Package and verification

开发包：`dev-package/`。包装清单 SHA256：`8437803a0d25423975c55515e4974cd3305442c622a371bdfba3ec242bf9a889`；PE SHA256：`173e2af3ff8ae274257306e9aa28b54662f9bf09c139893ffe1481ae0d6aca7c`。运行时清单固定 CLR、mscorlib、System、System.Core、System.ServiceProcess、System.Web.Extensions 的路径、SHA256 和文件版本；编译器与源码 SHA 单独记录。此处实际字节记录均是本地开发观察，不是生产批准。包中 source_commit 是开发树基线 4d394cb29eb174853867947c84365684ff60f5b1，尚不包含这些新增文件；集成固定提交后必须重新构建，不能将本包作为固定候选发布。
Development package: `dev-package/`. Manifest SHA256: `8437803a0d25423975c55515e4974cd3305442c622a371bdfba3ec242bf9a889`; PE SHA256: `173e2af3ff8ae274257306e9aa28b54662f9bf09c139893ffe1481ae0d6aca7c`. Runtime metadata pins paths, SHA256 and versions for CLR and five referenced framework assemblies. Compiler/source hashes are recorded separately. These are local observations, not approval. source_commit identifies the development-tree baseline and does not contain the new files; rebuild after the integrated source is committed. This package is not a fixed release candidate.

`python -B -m unittest test_disabled_host_package -q`：6 项通过（最新 0.856 秒）。包含真实 C# 编译、禁用配置 CLI 校验、真实隔离包构建、哈希/路径/大小写冲突/启用态拒绝与 PowerShell AST 解析；不是 Execute 分支的实机安装测试。开发构建命令另实际运行成功。未重复已有全量 833 比较；其旧结论不扩展到本新增代码。
Six tests passed (latest 0.856 seconds), including real C# compilation, disabled-config CLI validation, isolated staging, input/hash/path/case/enable rejection and PowerShell AST parsing. This is not live testing of the Execute branches. The real development build also succeeded. The prior 833-test comparison was not repeated or extended to this code.

## 安装与回滚边界 / Installation and rollback boundaries

所有存在的源包及目标祖先路径拒绝 reparse/junction；系统修改前及互斥锁内重新检查。身份为 NT SERVICE\RoktU1Bridge；代码仅服务 RX，状态服务 Modify，管理员和 SYSTEM 保留管理权限。服务默认 Disabled。回滚要求精确安装回执、清单哈希、账户、映像路径和 PE 哈希一致且服务已停，才删除本服务登记；保留代码、状态及所有账本，不恢复旧数据库。安装失败仅撤销本次创建且仍匹配的停用服务登记，不删除既有服务或状态。
Existing source/target ancestors reject reparse points and junctions, with checks repeated inside the install mutex. The virtual account is NT SERVICE\RoktU1Bridge; service code is RX and state is Modify, with administrative management retained. Start mode is Disabled. Rollback requires matching receipt, manifest hash, account, image and PE hash and a stopped service before removing this registration. Code, state and ledgers remain intact; no database restore occurs. Failed installation only removes the matching stopped registration created by that invocation.

## 尚缺与下一步 / Remaining gates and next steps

需要整体固定候选独立审核、正式发布器兼容及精确批准字节、真实目标运行时与有效 ACL/虚拟身份实机验证、原 Inventory 1784775229336 及原排他锁/唯一调度权威绑定。当前无可信生产 backend/信任根、非交互网络出口和真实跨登录/无人登录业务证据。框架六文件指纹是最小宿主观察，不宣称 Windows/.NET 全部传递依赖已封闭；U1 Python/SQLite/时区资源仍须独立清单及正式兼容验证。
The integrated fixed candidate needs independent review, publisher compatibility/approved bytes, target-runtime and effective ACL/virtual-account validation, and binding to the original Inventory and exclusive scheduling authority. Trusted production backend/root, noninteractive egress and live cross-login/unattended business evidence remain missing. Six framework fingerprints describe this minimal host; they do not prove complete Windows/.NET transitive closure. U1 Python/SQLite/timezone resources require a separate verified manifest.

最小管理员授权草案（尚未申请或执行）：在正式维护窗口、原权威互斥证明及固定包审核后，仅允许把固定哈希文件复制到新代码目录、建立隔离状态目录及上述最小 ACL、登记指定虚拟身份且 Disabled 的 RoktU1Bridge 服务；不启动、不启用、不改原 Inventory/旧服务/网络代理/SMTP/配额。回滚仅在所有权与停止状态验证后删除本次登记并保留状态。真正启动/无人登录验收需要单独可审核方案与批准，不能由本授权暗含。
Draft minimum administrator authorization (not requested or executed): after maintenance-window, original-authority exclusion and fixed-package review, permit only copying exact-hash files to the new code directory, creating isolated state/minimum ACLs, and registering RoktU1Bridge with the virtual account and Disabled start mode. No start/enable or changes to the original Inventory, old service, proxy, SMTP or quotas. Ownership-verified stopped registration removal preserves state. Starting and unattended acceptance require a separately reviewed and authorized plan.
