# U1 原发布器接线交付 / Original Publisher admission delivery

固定源码 / Fixed source: `d47e5d9f2f51bf0acc2f9dc4d3dc2a12b6287923`

## 实际工程 / Implemented engineering

原Publisher的Bearer认证、配置一致性seal与新增安装入口已在离线源码接通。批准仅来自受保护的原配置，HTTP不得提供任意命令、路径、摘要或授权。安装维护权取得、持续验证、进程证据、终态核验、释放与显式补偿接入同一调用路径；重复调用仅返回日志，不重复执行。seal是配置一致性校验，依赖受信本地所有权，并非密码签名或安装授权。
The original Publisher Bearer authentication, configuration-consistency seal and new installation admission are connected in offline source. Approval comes only from protected original configuration; HTTP cannot supply arbitrary commands, paths, hashes or grants. Maintenance acquisition, continuous verification, process evidence, terminal verification, release and explicit compensation share the connected path. Duplicate calls return journal evidence without re-execution. The seal checks configuration consistency and depends on trusted local ownership; it is neither a cryptographic signature nor an installation grant.

独审发现补偿子会话HELD时退出会被永久阻断。现以绑定完整会话日志、零进程意图的NO_PROCESS_INTENT证据修复；事务内再次核验证据以防竞争。仅根HELD可显式NOT_STARTED释放；补偿子会话必须以新恢复编号继续补偿，不能直接释放原维护权。INSTALL_INTENT无进程记录、LAUNCH-only等未知状态仍STOP_AND_PRESERVE。
Independent review found a blocked recovery when a compensation child exited at HELD. A NO_PROCESS_INTENT proof now binds the complete session journal and absence of process intent, with revalidation inside the transaction. Only a root HELD session may explicitly release as NOT_STARTED. A compensation child requires another recovery ID and cannot abandon the original authority. INSTALL_INTENT without process evidence and LAUNCH-only remain STOP_AND_PRESERVE.

## 测试与审核 / Tests and review

固定候选组合 **234/234通过**；独审 **94/94通过**，另六项探针通过。结论OFFLINE_SCOPED_REVIEW_PASSED，范围为已连接安装维护代码路径。HTTP成功路径使用安装/观察回调替身，协调器测试不能拼接成一次真实全安装验收。旧595候选的阻断诊断保留，不能继承其结果。
Fixed-candidate combined validation: **234/234 passed**. Independent validation: **94/94 passed**, plus six probes. OFFLINE_SCOPED_REVIEW_PASSED covers the connected installation-maintenance code path. HTTP success tests use installer/observer callback doubles; coordinator tests cannot be combined into a claim of one real end-to-end installation. The blocked 595 diagnostic is retained and its results are not inherited.

可比全量回归：基线`e279e5505a1526969ce1e1f4769cc11e02bce66d`及候选各833项，各37 failures、17 errors，失败和错误ID一致。NO_NEW_REGRESSION=true；ALL_GREEN=false。没有宣称全部通过。
Comparable full regression: baseline `e279e5505a1526969ce1e1f4769cc11e02bce66d` and candidate each ran 833 tests with 37 failures and 17 errors. Failure/error IDs match. NO_NEW_REGRESSION=true; ALL_GREEN=false. This is not an all-pass result.

## 工程包及摘要 / Engineering artifacts and hashes

真实AMD64工程包含71个载荷文件；原Publisher配套包含17个精确文件并通过实际解压后的新进程导入核验。原bin文件绑定旧SHA，新helper要求ABSENT；不扩大宿主文件白名单。两个包均不是完整可安装发布版，不含生产配置、凭据或通道自动更新器。外部CPython未捆绑。全部文件摘要见ARTIFACT_MANIFEST.json。
The actual AMD64 engineering package contains 71 payload files. The Publisher support archive contains 17 exact files and passed fresh-process import verification after extraction. Original bin members bind prior hashes; new helpers require ABSENT. The host allowlist is not expanded. Neither archive is a complete installable release; production configuration, credentials and a channel self-updater are absent. External CPython is not bundled. All file hashes are in ARTIFACT_MANIFEST.json.

- install.zip SHA256: `de61474814dad9acf252d0f75bce058be715743578f7e8514b738140cc676928`
- rollback-tools.zip SHA256: `40c414b4c9fd4af78ac356050efc9b6a1407d9417c67c59fc947ef880f62a4eb`
- Host manifest SHA256: `5d17d1cc7ec430cb60d20756efb2d5c7a8f5676a7eb9e3ee3f0952c75d7228b9`
- publisher-support.zip SHA256: `acb0db62e03128cd1dfe8434b65c98cd677e038b8f76c942f77bcffba617c2d9`
- Publisher manifest SHA256: `7639935e0c476a2ba1c58c165da4450734c85321da531014042ce827821bd73e`

## 剩余工程与验收 / Remaining engineering and acceptance

完成正式backend与原Inventory所有者/服务事件消费者的接线及合同核验；整合完整发布版后，在明确授权的隔离Windows环境验证真实首装、升级、中断恢复和回滚。
Complete formal-backend wiring to the original Inventory owner and service event consumer, including contract verification. Integrate the complete release, then validate real installation, upgrade, interruption recovery and rollback in an explicitly authorized isolated Windows environment.

正式backend当前仍为离线合同；原Inventory所有者至正式服务事件消费者的实际执行链尚未完成。原Inventory和原Publisher准入补丁必须在同一受控窗口交付并刷新受信配置/seal，当前未执行。实际PowerShell入口、SCM/ACL成功路径、无人值守生命周期尚未验证。WorkBuddy下一步仅针对最终完整候选和新增行为核验，不重复索要已消费P1证据；当前不启动现场验收或生产安装。
The backend remains an offline contract; the actual execution chain from the original Inventory owner to the formal service event consumer is incomplete. Original Inventory and Publisher admission patches require the same controlled rollout window and trusted configuration/seal refresh; none was applied. Real PowerShell entry, successful SCM/ACL paths and unattended lifecycle remain unverified. WorkBuddy should verify the final complete candidate and new behavior without repeating consumed P1 evidence. Site acceptance and production installation are not started now.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

接受既定非对称ACL裁决。本轮仅离线开发和隔离测试，未修改现场发布器、生产数据库/账本/ACL/目录/服务/Inventory或系统配置。
The accepted asymmetric ACL ruling is retained. This work used offline development and isolated tests only, without changing the site Publisher, production database/ledger/ACL/directories/services/Inventory or system configuration.
