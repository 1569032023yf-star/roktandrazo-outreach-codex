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
