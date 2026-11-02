# U1 安装所有权修复 / Installation ownership repair

时间 / Time: 2026-11-02T08:49:26.631992+00:00
固定源码 / Fixed source: dcbddc3fe5535b39d789eba61df94f651aa2bd34

中文：安装器将所有权凭据从服务可修改的 ProgramData 移至代码目录 config/installation.json（预期服务只读）。使用 CreateNew、持久刷新及逐字节读回，拒绝覆盖。回滚读取凭据和执行文件时持有只读共享句柄，哈希基于该句柄读取的字节，直到回滚退出才释放。未修改生产服务、数据库、Inventory 或 SMTP。
English: The installer moves ownership evidence from service-writable ProgramData to config/installation.json in the code tree (intended read-only to the service). CreateNew, durable flush and byte readback refuse replacement. Rollback holds read-shared handles for the receipt and executable, hashes bytes read from those handles, and retains them until exit. No production service, database, Inventory or SMTP was changed.

验证 / Validation: python -B -m unittest test_u1_provision test_disabled_host_package -q — 8 PASS, 2.725s. 实际隔离文件验证凭据写入、拒绝覆盖、双文件写入封锁，以及 PowerShell 语法和真实 PE 编译。Actual isolated filesystem checks cover receipt creation, overwrite refusal and write blocking for both pinned files, plus PowerShell parsing and real PE compilation.

限制 / Limits: 此修复不证明实际 ACL 已验收，也不解决祖先目录/硬链接的全部竞争。旧 ProgramData 凭据不自动采纳。完整文件回滚、SCM 升级、宿主与原 Inventory 的执行接线仍未完成。新候选未重打安装包、未独审、未安装；旧包不得视为包含此修复。
This repair does not establish deployed ACL acceptance or eliminate every ancestor/hardlink race. Legacy ProgramData receipts are not automatically adopted. Full-file rollback, SCM upgrades and host execution wiring to the original Inventory remain incomplete. The new candidate has not been repackaged, independently reviewed or installed; old packages do not contain this fix.

下一步 / Next: 完成 SCM 升级与完整文件回滚，再冻结重打包并独审；继续原 Inventory 拥有者与执行宿主的接线，保持派发关闭。Finish SCM upgrade/full-file rollback, then freeze, rebuild packages and obtain independent review; continue existing Inventory-owner/host wiring with dispatch closed.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false
