
## 干净源码对照复验 / Clean-source comparison
中文：固定基线20项通过（28.041秒）；固定候选23项通过（28.211秒），包含新增3项。使用各自Git固定源码的独立目录，未跳过静态扫描、未更改白名单，旧缺文件错误未复现。仅本组无新增失败；不是完整回归或独立审核。
English: Pinned baseline passed 20 tests in 28.041 seconds; candidate passed 23 in 28.211 seconds, including three new tests. Separate pinned Git trees were used, without skipping the static scanner or changing its allowlist. The old missing-file error did not reproduce. No new failure in this group only; not full regression or independent review.

# U1 三阶段连续开发核对 / U1 continuous-development reconciliation

中文：2026-11-04当前工程源码固定为032e2198d124fea2e40ace2f109574e9a92016a8，已含6c60dba Publisher修复。第一阶段完成一个范围明确的UNKNOWN传输修复，3项定向测试通过；正式Provider、权威费用、SAFE来源及崩溃窗口仍未完成。详见autonomy/evidence/u1_provider_transport_20261104/REPORT.md，所有历史证据保留。
English: Current engineering source is 032e2198d124fea2e40ace2f109574e9a92016a8, including the Publisher fix. Phase 1 adds a scoped UNKNOWN transport fix with three focused passing tests. Formal Provider, authoritative cost, SAFE provenance and the crash window remain incomplete. See autonomy/evidence/u1_provider_transport_20261104/REPORT.md; all historical evidence is retained.

中文：任务队列中的3fbaa5e包只保留为历史产物；当前已知owner服务工程包基线59acb7a，二者都不是当前完整发布包。当前候选包NOT_BUILT，CPython和完整依赖未集成。独审PENDING；最终全量NOT_RUN。Windows和费用请求均无新授权。
English: Queue references to the 3fbaa5e package are historical artifacts. The known owner-service engineering archive baseline is 59acb7a; neither is a complete current release. Current package NOT_BUILT, with CPython and full dependencies outstanding. Review PENDING; final full regression NOT_RUN. No new Windows-install or chargeable-request authority.

DEVELOPMENT_COMPLETE=false; PACKAGE_COMPLETE=false; PROVIDER_ACCEPTED=false; WINDOWS_ACCEPTED=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; smtp_enabled=false.

---

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

---

# U1 原owner服务工程包 / Original-owner service engineering package

固定源码 / Fixed source: 59acb7a1c422841b71f82019cd52a5e66daa6d7e | 2026-11-03T21:10:57.755730+00:00

重建真实AMD64禁用工程包，纳入原数据库只读入口、runtime plan到bootstrap参数传递。73份manifest文件逐SHA256核验，安装及回滚zip逐字节对照解包树通过，PE machine AMD64。包内源码经隔离Python路径加载，15项HTTP/子进程/预算/配置测试通过，11.722s；外层12.185s。结果见VALIDATION.json及PACKAGED_TEST_OUTPUT.txt。
Rebuilt the actual AMD64 disabled engineering package with original-DB read-only bootstrap and runtime-plan argument propagation. All 73 manifest files passed SHA256 checks, both archives matched their staging bytes, and the PE machine is AMD64. Isolated Python loading of packaged source passed 15 HTTP/process/budget/configuration tests in 11.722s (12.185s outer wall time). See validation and output files.

安装包 / Install SHA256: b3b79f6e526dc9055d4b8916c39931a01853e3374715b103be6508de89c4d5f8
回滚工具 / Rollback SHA256: 6521f8e0c2c2303016ef2d95ea012316f2f18d2ed1e664d5c4f5864e083ee116
Manifest SHA256: bd16b71edde13711eac7ecf78a304f3ed9db996d0e4012e76e9d74b927c7c0b0

本次交付为工程包，未捆绑CPython或完整业务依赖。未运行真实服务启动、正式Provider或实际费用验收。独审PENDING，全量回归NOT_RUN_FOR_THIS_SHA；不继承旧审核及833项结果。
This engineering archive does not bundle CPython or complete business dependencies. Real service startup, formal Provider and measured-cost acceptance were not run. Independent review PENDING and full regression NOT_RUN_FOR_THIS_SHA; previous reviews and 833-test results are not inherited.

下一步 / Next: 完成此固定包的服务bootstrap生命周期验证与独审，再接通正式Provider和实测费用；生产安装未授权。
Complete pinned service-bootstrap lifecycle validation and independent review for this fixed package, then integrate formal Provider execution and measured costs. No production installation is authorized.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.

无生产数据库、ACL、服务或Inventory操作；本地测试均为临时fixture，现有WorkBuddy证据复用。
No production database, ACL, service or Inventory operation occurred. Local tests used temporary fixtures and existing WorkBuddy evidence was reused.

---
# U1 服务原所有者配置 / Service original-owner configuration

固定源码 / Fixed source: 229c48c2d44cf18a12e9c6f9049d40847349e9ec | 2026-11-03T18:10:57.037585+00:00

实际接线：安装准备器从独立hash绑定的runtime plan提取original_owner_db，生成runtime.json并纳入supervisor的runtime_config_sha256；固定bootstrap将该引用传至宿主--original-owner-db。原owner与离线event_runtime互斥。准备器验证绝对规范路径、存在文件及reparse祖先；不复制、hash锁定或写入可变原数据库。
Implementation: installation preparation propagates original_owner_db from the separately hash-bound runtime plan into runtime.json and the supervisor runtime_config_sha256. The pinned bootstrap forwards it to the host --original-owner-db argument. Original-owner and offline event_runtime references are mutually exclusive. Preparation checks canonical absolute existing-file paths and reparse ancestors without copying, hash-locking or writing mutable database bytes.

验证 / Validation: python -B -m unittest test_u1_provision test_u1_host_runtime -q: 5 PASS, 5.188s. Actual PowerShell config generation verifies propagation, source bytes preserved and dual-authority rejection. Complete service bootstrap execution was not tested this round.

本SHA独审PENDING；全量NOT_RUN；安装包未重建，旧审核/包不继承。非完整发布验收。
Independent review PENDING for this SHA; full regression NOT_RUN; packages not rebuilt and previous reviews/archives not inherited. This is not complete release acceptance.

下一步 / Next: 通过完整固定bootstrap核验生成的服务配置，重建候选并独审；继续完成正式Provider及实测费用接线。
Validate the generated service configuration through the complete pinned bootstrap, rebuild the fixed candidate and obtain independent review; formal Provider and measured-cost integration remain required.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
未修改生产数据库、ACL或服务，未触发Inventory；复用WorkBuddy既有证据。
No production database, ACL or service changed; no Inventory triggered. Existing WorkBuddy evidence reused.

---
# U1 原所有者启动接线 / Original-owner bootstrap wiring

固定源码 / Fixed source: 748ccb0196786884611cb98fab97888e6a12d231 | 2026-11-03T15:10:42.508166+00:00

启动入口新增互斥--original-owner-db与--event-runtime，将原数据库只读连接接到既有open_host原owner观察器；不再仅能通过测试内注入连接工厂。绝对路径、普通文件、单硬链接、启动时文件身份固定及连接前后复验；mode=ro和query_only禁止建库、迁移及写入。
The host CLI now accepts mutually exclusive --original-owner-db and --event-runtime, routing a read-only original database connection to the existing owner observer instead of requiring test-only connection injection. It requires an absolute ordinary single-link file, captures file identity and checks it around connections. mode=ro and query_only prevent database creation, migration and writes.

路径身份检查依赖受信配置和受保护目录，不声明对敌对目录的完整TOCTOU防护。未放开生产执行或服务安装；固定服务runtime plan及supervisor参数仍待接线，正式Provider及实测费用仍未完成。
Path checks depend on trusted configuration and protected directories; they do not establish complete TOCTOU protection against hostile directory mutation. Production execution and service installation remain disabled. Pinned runtime-plan and supervisor arguments, formal Provider and measured costs remain incomplete.

验证 / Validation: python -B -m unittest test_u1_host_runtime test_original_process_backend test_inventory_event_bridge -q: 13 PASS, 7.775s. Actual SQLite missing-file/no-creation, write rejection and file-replacement checks plus existing HTTP/child/settlement integration.

本SHA独审PENDING，全量回归NOT_RUN，安装包未重建；不继承3fbaa5e审核或旧包。
Independent review PENDING for this SHA, full regression NOT_RUN, packages not rebuilt. The 3fbaa5e review and old packages are not inherited.

下一步 / Next: 把获准原owner数据库引用接入固定服务runtime plan与supervisor参数；完成正式Provider与实测费用合同后重建并审核完整发布版。
Wire the approved original-owner DB reference into the pinned service runtime plan and supervisor arguments; complete formal Provider and measured-cost contracts before rebuilding and reviewing the complete release.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336.

本轮未操作生产数据库、服务、ACL或Inventory；复用既有WorkBuddy证据，不重复消费回执。平台硬超时未配置，不声明已强制45分钟。
No production database, service, ACL or Inventory operation occurred. Existing WorkBuddy evidence was reused without duplicate receipts. No platform hard timeout was configured or claimed.

---
# U1 原执行链交付 / Original execution-chain delivery

固定源码 / Fixed source: `3fbaa5ec42cb0655ecd1c811ccd8d02b1fc837bb`

中文：已将原stage接入持有既有Inventory权利的事件消费者，路径为原stage→HTTP→原owner适配器→受控子进程→预算结算→原job终态与释放同事务。错误owner、日期、原DB身份及非running任务均在调用backend前拒绝。子进程运行期间持续检查原owner，丢权时终止进程树并保留UNKNOWN。未知收据或丢ACK不重放、不回落旧业务入口。

English: The original stage now consumes events under its existing Inventory authority: original stage → HTTP → original-owner adapter → controlled child → budget settlement → atomic original-job finalization and release. Incorrect owner, date, DB identity or non-running jobs are rejected before backend invocation. Runtime owner loss stops the process tree and preserves UNKNOWN. Unknown receipts and lost ACKs authorize neither replay nor fallback to the legacy body.

中文：独审发现的先提交job成功、后发现释放失败问题已修复。写入失败及释放零行均回滚整个事务；原job保持running、原锁保留、backend只执行一次。实际进程树控制已测试；业务worker、签名及SAFE库存计数仍为隔离fixture，正式Provider和真实费用合同尚未接通。

English: Independent review found premature job success before release verification. Both job-write failure and a zero-row release now roll back the complete transaction, preserving the running job and original lock with only one backend invocation. Real process-tree control was tested; business workers, signatures and SAFE counts remain isolated fixtures. Formal Provider execution and measured-cost contracts remain incomplete.

组合测试 / Combined tests: 271 tests; passed=True; failures=0; errors=0; skips=0. 每项结果见validation；新候选重新运行。 / Per-test output is under validation; this candidate was rerun.

独立审核 / Independent review: OFFLINE_SCOPED_REVIEW_PASSED; {'count': 76, 'duration_seconds': 30.374, 'duration_basis': 'sum of two independent unittest runner durations, not elapsed wall time', 'failures': 0, 'errors': 0, 'runs': [{'command': 'python -m unittest test_original_stage_event test_original_inventory_owner test_inventory_maintenance tests.test_inventory_stage_trace tests.test_phase4a8r_continuous_discovery -q', 'count': 60, 'duration_seconds': 18.916}, {'command': 'python -m unittest test_original_process_backend test_process_backend test_inventory_event_bridge -q', 'count': 16, 'duration_seconds': 11.458}]}. 详见review-3fbaa5e，旧候选失败报告保留。 / See review-3fbaa5e; previous failed-candidate reports are retained.

可比全量 / Comparable full regression: baseline `68788653c848659c63f85021075fedee4aca5b13` / candidate `3fbaa5ec42cb0655ecd1c811ccd8d02b1fc837bb`; tests 833/833; failures 37/37; errors 17/17; NO_NEW_REGRESSION=True; ALL_GREEN=False. 不宣称全绿。 / No all-green claim.

真实AMD64工程包 / Actual AMD64 engineering package: 73 payload files.
- install.zip SHA256: `16410c14c094ee3452abe0506257236b61de2e1769447e282503e7fcaa17ccb7`
- rollback-tools.zip SHA256: `0614261b9c1ddaa2dee43be28c4390db9d1b32f11bc6a26b0ea058751ad4395b`
- host manifest SHA256: `85a59889bdeaa4097e92393525f3ad87ceda70090b28d2246cb20a430d397bec`
- 17-file companion SHA256: `c4adf386d86b8a70b8833c51e51148cee1ea74ffee0858e08b41777dddb6bab7`
- companion manifest SHA256: `c7e0b3aa943cd06ae1948745d14a03c58375ff37f4cb9d12c879585e764b59cb`

中文：每文件摘要见ARTIFACT_MANIFEST.json；独立包审核见review-3fbaa5e。配套包只含固定路径源码，不是更新器，不扩大旧Publisher白名单；expected_before来自固定Git基线，不是现场证据。未捆绑外部CPython及完整业务依赖，不是完整可安装发布版。

English: ARTIFACT_MANIFEST.json records per-file digests; review-3fbaa5e contains independent package checks. The companion includes fixed source paths only; it is not an updater and does not expand the old Publisher allowlist. expected_before comes from a pinned Git baseline, not site evidence. External CPython and complete business dependencies are not bundled; this is not a complete installable release.

待完成及真实安装门禁 / Remaining engineering and installation gates:
完成正式Provider执行、费用实测和受信运行配置，随后对完整候选审核；经授权后由WorkBuddy进行隔离Windows首次安装、升级、进程退出恢复、回滚中断恢复及Disabled/Stopped验收。不得用测试worker或SAFE替身代替业务验收。

Complete formal Provider execution, measured costs and trusted runtime configuration, then review the complete candidate. After authorization, WorkBuddy verifies isolated Windows first installation, upgrade, process-exit recovery, interrupted rollback and Disabled/Stopped state. Test workers and SAFE fixtures are not business acceptance.

中文：本轮未安装/启动服务、未修改生产ACL/数据库/账本/Inventory。现有安装器事务测试不等同于WorkBuddy真实Windows无人值守成功验收。保留已接受的非对称ACL裁决。

WorkBuddy后续具体核验（完整候选审完且另行授权后） / Specific later WorkBuddy checks (after complete-candidate review and separate authorization):
1. 隔离Windows核对固定commit、安装包/manifest/运行时身份；保留安装前文件和ACL快照。 / In isolated Windows, verify commit, archive/manifest/runtime identities and retain pre-install file/ACL snapshots.
2. 首装核对两个根目录的非对称ACL、自有文件收据以及服务Disabled/Stopped；升级覆盖新增、替换、删除。 / Check asymmetric root ACLs, owned-file receipts and Disabled/Stopped registration; upgrade must cover creation, replacement and deletion.
3. 在持久intent、实际写入、回执与回滚边界注入退出，再重启安装进程；ABSENT须恢复，未知状态必须STOP_AND_PRESERVE。 / Terminate at durable-intent, mutation, receipt and rollback boundaries, then restart the installer; restore ABSENT and preserve unknown states.
4. 核实维护权取得、持续持有、最终读回和精确释放；原Inventory占用或UNKNOWN时不得取得安装权。 / Verify maintenance acquisition, continuous holding, final readback and exact release; a held/UNKNOWN original Inventory must deny installation authority.
5. 不触发生产Inventory；无人值守业务验收必须待正式Provider链与独立授权完成，单独记录实际请求、费用、取消和结算证据。 / Do not trigger production Inventory; unattended business acceptance awaits the formal Provider chain and authorization, with separate actual request, cost, cancellation and settlement evidence.

English: No service was installed/started and no production ACL, DB, ledger or Inventory was modified. Installer transaction tests do not establish WorkBuddy's real Windows unattended acceptance. The accepted asymmetric ACL ruling remains unchanged.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
