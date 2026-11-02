# U1执行接线与安装阻断修复 / U1 execution wiring and installation blocker fixes

更新时间 / Updated: 2026-11-02T08:40:48.546343+00:00
固定源码 / Pinned source: `cc9b7a7b672eb2098fa02d7e57c266b4ec57d76e`

实际代码 / Implemented code:
- ProcessBackend通过现有Job进程树运行固定哈希Python/worker；有界stdin传操作，不放入命令行。执行前提交IN_FLIGHT，进程中断、超时、丢失回执保留UNKNOWN；同identity不重放。正常返回仅缓存传输输出，现有SingleSlotAdapter仍验证签名和run/claim后才结算。
- ProcessBackend runs pinned Python/worker through the existing Job process tree, sending bounded stdin instead of operation-bearing argv. IN_FLIGHT commits before launch; crashes/timeouts/missing receipts remain UNKNOWN without replay. Cached output is transport evidence only; SingleSlotAdapter authenticates signed run/claim receipts before settlement.
- 原Inventory事件适配入口强制复用已持有的supervisor锁；不创建调度器或租约，不接受其他Inventory。新增只读恢复状态，不授予重放/退款/生产终态权限。
- Existing-Inventory event consumption requires the already-held supervisor lease. No new scheduler/lease, foreign Inventory, replay/refund or terminal authority is introduced.
- 安装器持有包清单、文件、配置计划与Python/token/snapshot依赖的只读句柄直至结束，实际测试写入被拒绝。修复最终SHA目录比暂存UUID目录更长造成的Windows路径故障，stage前预检最终布局。
- Installer pins manifest/artifacts/plan and Python/token/snapshot dependencies read-only through completion; mutation attempts were rejected in testing. Final SHA paths are now checked before staging, fixing the observed longer-final-directory Windows path failure.

验证 / Validation:
- 当前固定源码84项组合通过，47.799秒；包内实际模块5项通过，2.215秒。均为开发验证，不是独审。
- Current pinned source:84 combined tests passed in47.799s;5 tests loading the actual packaged module passed in2.215s. These are development checks, not independent review.
- 基线与本候选各833项，同37失败17错误，ID完全一致，新增失败/错误0，非全绿；覆盖tests/。参见FINAL_COMPARISON.json及两份result。历史6b9c255比较单独保留。
- Both baseline/current candidate ran833 tests with identical37 failure/17 error IDs and zero new IDs, not all green; scope tests/. See FINAL_COMPARISON.json and both result files. Intermediate6b9c255 evidence is retained separately.
- 60文件真实包已stage、bootstrap逐文件核验、包内执行测试、回滚ABSENT通过。首次检查6002a5b在深目录触发路径故障；另一次验证脚本未加-B生成pycache，被UNMANAGED_FILES正确拒绝。按真实服务-I -B方式重新验证通过，旧隔离目录保留。
- The60-file real package passed staging, bootstrap verification, packaged execution tests and rollback to ABSENT. An initial6002a5b deep-root check exposed the path bug; a separate harness without-B generated pycache and was correctly rejected as UNMANAGED_FILES. Verification using the service's-I -B policy passed; old isolated directories are preserved.

安装ZIP / Install ZIP SHA256: `046cfd72d783bf09dac704a5b359b03421933f90d1078c2a8dd297a3f89e33be`
回滚工具ZIP / Rollback tools ZIP SHA256: `8cfec97c4bafd5a200ab2a5f3147edb58d2da66dd104697a95586003080cf76e`
清单 / Manifest SHA256: `11481e186c7556bf406eb41ed1c0589daf560906ff1b23e6c6c7468cb870e219`

剩余交付阻断 / Remaining delivery blockers:
正式服务/8791与原Inventory拥有者尚未接入该离线事件入口；生产backend准入、身份/ACL、Python依赖不可变保护、SCM升级和完整文件回滚仍未闭环。Windows临时stdin可能有磁盘临时文件，生产ACL必须验证。文件句柄pin不证明全部祖先目录/硬链接/TOCTOU与维护租约安全。独审PENDING，未安装、启用、部署服务。回滚工具包依赖现场versions/backups，不是完整现场备份。
Formal service/8791 and original Inventory owner are not yet wired to this offline event consumer. Production backend admission, identity/ACL, immutable Python dependencies, SCM upgrade and complete file rollback remain open. Windows temporary stdin can be disk-backed and requires production ACL verification. File pins do not establish complete ancestor/hardlink/TOCTOU or maintenance-lease safety. Independent review PENDING; no service installation, enabling or deployment. Rollback tools depend on retained site versions/backups and are not a complete site backup.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false

下一动作：接通原Inventory拥有者与宿主事件消费入口，保持派发门禁关闭；补齐身份/ACL/依赖保护及SCM升级和完整文件回滚，固定候选独审后才安装。
Next action: Wire the existing Inventory owner to the service event consumer with closed dispatch gates; finish identity/ACL/dependency protection and SCM upgrade/full-file rollback, then independently review the frozen candidate before installation.
