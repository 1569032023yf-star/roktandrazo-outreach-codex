# U1 发布器原owner配置接线 / Publisher original-owner plan wiring

时间 / Time: 2026-11-04T00:14:46.188985+00:00
固定源码 / Fixed source: 6c60dba1f70f998ad933510750aba865597c8c12

修复正式发布器拒绝 original_owner_db 的实际阻断项，使其与安装器及服务bootstrap已经支持的计划一致。event_runtime 与 original_owner_db 继续互斥。原数据库以Windows只读访问句柄固定文件身份，共享读写但拒绝删除；不读取、哈希、复制、迁移或修改数据库。保持祖先目录固定、普通文件与单硬链接校验，并在执行前重新验证。安装与派发门禁不变。
Fixed a real publisher admission blocker: original_owner_db plans now reach the existing installer and bootstrap path. Owner sources remain mutually exclusive. A Windows read-access handle pins database identity while sharing reads/writes and denying deletion. No database bytes are read, hashed, copied, migrated or changed. Ancestor identity, ordinary-file and single-link checks remain enforced and are revalidated before execution. Installation and dispatch gates remain closed.

定向验证 / Targeted validation:
- python -B -m unittest test_install_command test_install_inputs test_u1_provision test_u1_host_runtime -q: 17 PASS, 9.726s (before final added link/missing-path test).
- python -B -m unittest test_install_inputs test_install_command -q: 13 PASS, 5.686s (final source).
- python -B -m unittest test_install_contract test_install_journal test_install_process test_install_verifier test_publisher_install_admission test_publisher_install_maintenance -q: 54 PASS, 75.812s.

真实临时SQLite连接在固定期间提交写入成功；unlink/rename拒绝，释放固定且关闭数据库后rename成功；双owner配置、硬链接、缺失路径及冲突固定被拒绝，缺失数据库不创建。
An actual temporary SQLite connection committed writes while pinned; unlink/rename failed until pin release and database close. Dual-owner configuration, hardlinks, absent paths and conflicting pins were rejected without creating an absent database.

故障记录 / Fault record: initial attribute-only handle did not reliably exclude deletion; changed to read-access handle and reran real Windows checks successfully. 初版属性句柄未能拒绝删除，已改为只读访问句柄并通过真实Windows复验。

独审 / Independent review: PENDING. 全量 / Full regression: NOT_RUN_FOR_THIS_SHA. 不继承旧833及独审结论 / No inherited 833-test or review acceptance.
本次修改正式发布器源码，不重建未包含publisher_channel的既有宿主工程包；旧包固定源码59acb7a1c422841b71f82019cd52a5e66daa6d7e，安装SHA b3b79f6e526dc9055d4b8916c39931a01853e3374715b103be6508de89c4d5f8，回滚工具SHA 6521f8e0c2c2303016ef2d95ea012316f2f18d2ed1e664d5c4f5864e083ee116。它们不代表本次发布器版本已打包验收。
This change is publisher source only; the existing host archives do not contain publisher_channel and were not rebuilt. The above existing archive hashes remain scoped to their prior source and do not certify this publisher revision.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; smtp_enabled=false.

未运行生产采集、服务安装、启用、生产DB操作；唯一Inventory不变。未配置平台硬45分钟超时，平台任务无该字段。
No production collection, service install/enablement or production DB operations were performed; the sole Inventory is unchanged. No platform hard 45-minute timeout was configured because the task has no such field.

GitHub指令评论本轮刷新失败（gh未安装，网页读取cache miss）；按用户当前明确冻结范围继续离线修复，未推断新增权限。
The instruction comment could not be refreshed (gh unavailable; web cache miss). Offline work stayed within the user's explicit current frozen scope without inferring new authority.

下一动作 / Next action: 验证固定服务bootstrap生命周期并完成发布器、安装器及宿主链独审；正式Provider及实测费用仍待接通，生产安装未授权。
Validate the fixed service bootstrap lifecycle and obtain independent review of the publisher/installer/host chain; formal Provider execution and measured costs remain outstanding. No production installation is authorized.
