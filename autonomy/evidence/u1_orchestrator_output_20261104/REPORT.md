# U1 原入口输出边界 / Original entry output boundary

时间 / Time: 2026-11-04T10:13:40.048976+00:00
固定源码 / Fixed source: 5b56b3d1a903f10726304599d0d9bfd1c1df698b

中文：移除 bd_orchestrator 导入时创建代码目录 output 的副作用；新增 --output-dir 显式绝对报告路径参数，拒绝相对路径，启动选择路径时不创建目录。仅在原 end-of-day 报告写入边界创建输出目录。未提供参数时保留旧路径兼容。此参数不授予路径权限，也不替代安装器的目标路径、ACL和reparse校验。
English: Removed code-root output creation during bd_orchestrator import. Added an explicit absolute --output-dir report path, rejecting relative paths and creating nothing during selection. Directory creation occurs only at the existing end-of-day report boundary. Omission retains the legacy path. This argument grants no path permissions and does not replace installer target, ACL or reparse checks.

验证 / Validation:
- python -B -m unittest test_orchestrator_output_boundary -q: 2 PASS.
- python -B -m unittest test_orchestrator_output_boundary test_original_inventory_owner -q: 14 PASS / 4.043s.
- python -B -m unittest test_orchestrator_output_boundary test_inventory_event_bridge test_original_inventory_owner -q: 21 tests, 6 ERROR: DEVELOPMENT_EXTERNAL_TRANSPORT_DISABLED. 保留护栏，不绕过 / Guard retained without bypass.
- git diff --check: PASS.

中文：测试在临时目录执行真实入口源码，隔离数据库及配置导入，不运行生产阶段。未重建安装包，旧3f02af1包不代表本源码；新候选全量未执行，独审PENDING。凭据仍由既有env_loader加载，尚未分离至批准配置；新参数尚未由固定宿主计划传入，完整owner到worker闭环未完成。没有安装、启动服务、采集、生产数据库写入、SMTP或敏感信息输出。
English: Tests execute actual entry source in temporary storage with isolated database/config imports and no production stage. No archive was rebuilt; the old3f02af1 archive does not represent this source. Full candidate regression NOT_RUN; independent review PENDING. Existing env_loader still loads credentials; approved configuration separation and pinned host propagation of the new argument remain unfinished. The complete owner-to-worker chain is not accepted. No installation, service activation, collection, production DB writes, SMTP or sensitive output occurred.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_install=false
allow_dispatch=false
allow_cancel_dispatch=false
SMTP=false

下一步：将原入口凭据加载分离至批准配置合同，再把明确状态输出路径纳入固定宿主调用；不复制生产.env、不跳过权限。
Next: separate original-entry credential loading into the approved configuration contract, then propagate the explicit state output path through the pinned host invocation without copying production .env or bypassing permissions.
