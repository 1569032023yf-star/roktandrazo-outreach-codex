# U1 离线交付说明 / U1 offline delivery guide

本说明不构成安装授权。检查 DELIVERY.json 的固定源码与门禁；仅 python_runtime_bundled=true 的候选包含完整固定 CPython。正式合同缺失时保持 CONTRACT_MISSING，离线 Worker、签名、费用计数和回执 fixture 不构成正式业务证据。

This guide does not authorize installation. Check the fixed source and gates in DELIVERY.json. Only python_runtime_bundled=true candidates contain pinned full CPython. Keep CONTRACT_MISSING for missing formal contracts; offline workers, signatures, usage counters and receipt fixtures are not formal business evidence.

## 身份与依赖 / Identity and dependencies

分别核对 install.zip 和 rollback-tools.zip 的批准 SHA256。核对外层 manifest.json 摘要、source_commit、inventory_id=1784775229336 和全部 payload 文件，以及嵌套 host/manifest.json 与 runtime/python/U1_RUNTIME_CONTENT.json。不得混用旧版本验收结果。

Independently verify approved SHA256 values for both archives. Check the outer manifest digest, source_commit, inventory_id=1784775229336 and every payload file, plus nested host and Python-content manifests. Never transfer acceptance from another source version.

dependencies/ 固定已选输入的版本与摘要，不证明完整业务依赖闭包。wheel 清单不包含浏览器二进制；Playwright 导入成功不等于浏览器可运行。包内不应包含真实凭证。

dependencies/ locks versions and hashes of selected inputs, not complete business import closure. The wheel lock does not bundle browser binaries; Playwright import success does not establish browser operation. Production credentials must not be packaged.

## 离线核验 / Offline checks

解压到新目录，不覆盖已有现场。用包内 Python -I -B 检查启动、导入及子进程，并核对模块来源位于解压目录。使用包内 Python -m pip --isolated --disable-pip-version-check check。原生 --validate-runtime 仅验证运行时，不注册服务。回环 HTTP 临时 fixture/随机端口不代替正式 Provider、7877、8791、开机、注销或 Session 0 验收；拒绝和超时保留失败/UNKNOWN。

Extract into a new directory. Use packaged Python -I -B for startup, imports and subprocess checks, verifying module origins inside extraction. Use packaged Python -m pip --isolated --disable-pip-version-check check. Native --validate-runtime validates runtime only and does not register services. Loopback fixtures and ephemeral ports do not establish formal Provider, 7877/8791, reboot, logout or Session 0 acceptance. Preserve failed/UNKNOWN outcomes.

## 安装前提 / Installation prerequisites

固定候选独立审核、完整回归、整包核验与单独授权后，才可在隔离 Windows 安装。保持现有六字段批准协议。v3 运行计划绑定包内 Python 源路径与宿主清单，Supervisor 指向安装后的 Code Root。令牌、快照、运行计划和原 Owner 数据库引用由授权现场提供。Publisher 必须提供绑定原 Inventory 的有效 MaintenanceAuthority；不能直接复制 -Execute 命令绕过。

Install only in isolated Windows after fixed-candidate independent review, full regression, package verification and separate authorization. Preserve the existing six-field approval protocol. A v3 plan binds packaged Python source paths to host identity and Supervisor to installed Code Root. Authorized site inputs supply tokens, snapshots, plans and original-owner database references. Publisher must supply a live MaintenanceAuthority bound to original Inventory; copying an -Execute command cannot bypass it.

Code Root 继承并增加服务 RX；State Root 断开继承并移除普通用户写权限。allow_install、allow_dispatch、allow_cancel_dispatch、smtp_enabled 全部保持 false，直到分别获得授权。

Preserve asymmetric ACLs: Code Root inherits plus service RX; State Root breaks inheritance and removes ordinary-user write. Keep all four gates false until separately authorized.

## 回滚与恢复 / Rollback and recovery

保留原审计日志、事务 blob、安装回执、批准清单、运行计划及现场备份。回滚包是工具，不是数据库或现场备份。release_store.py rollback 只恢复发布指针；旧 Rollback-DisabledHost.ps1 只撤销服务注册，均不能宣称完整回滚。完整补偿使用原安装事务 Rollback/RecoverInstall 路径，仍需相同身份绑定、有效维护授权和单独执行授权。

Retain audit journals, transaction blobs, receipts, approved manifests, plans and site backups. The rollback archive is tooling, not a database/site backup. release_store.py rollback restores a pointer only; legacy Rollback-DisabledHost.ps1 removes registration only. Complete compensation uses original transaction Rollback/RecoverInstall paths with identity bindings, live maintenance authority and separate authorization.

UNKNOWN 必须 STOP_AND_PRESERVE，保留原锁和预算预留，禁止自动重放、删除未决日志或覆盖未知文件。不得修改生产数据库、ACL、服务或触发真实派发、取消、SMTP、扣费。

UNKNOWN requires STOP_AND_PRESERVE with original locks and budget reservations retained. Never automatically replay, delete pending journals or overwrite unknown files. Do not modify production databases, ACLs or services, or trigger real dispatch, cancellation, SMTP or charges.
