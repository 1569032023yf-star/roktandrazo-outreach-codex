# U1 安装与宿主接线 / Installation and host wiring

时间 / Time: 2026-11-04T11:28:41.327647+00:00
固定源码 / Fixed source: 69eb1887800f046b6d860cbefad6bd99f3c35169

中文：实际安装计划新增成对Provider配置绝对路径/批准SHA256，经生成runtime.json、bootstrap参数进入宿主。安装器与宿主使用Windows输入固定；宿主持有配置和祖先句柄直至退出，验证失败在快照/owner/监听前拒绝；不把密钥写入runtime.json、服务环境或HTTP。原业务Worker尚未接收该配置，不声称自动执行已完成。
English: Paired absolute Provider configuration path/approved SHA256 now flows from the actual installation plan through generated runtime.json and bootstrap into the host. Installer and host use Windows input pins; the host holds file/ancestor handles until exit and rejects invalid input before snapshot/owner/listener access. Credentials are not written to runtime.json, service environment or HTTP. The original business Worker does not yet receive this reference; automatic execution is not claimed complete.

中文：修复真实Publisher安装验收仍用Base64读取外置块字典以及512文件上限两个P0阻断。复用文件事务decoder核查固定operation日志旁的块存储身份和内容SHA，不添加任意路径或重放能力；上限与8192包文件加2生成配置一致。42项定向组合全部通过，包括真实临时文件首装、升级、两类回滚及块篡改后保留UNKNOWN维护锁。SCM/ACL为隔离替身，不能替代Windows安装验收。
English: Repairs two P0 Publisher acceptance blockers: decoding actual blob references as Base64 and a512-file limit. Reuses the transaction decoder to verify sibling blob-store identity/content hashes for the fixed operation journal; no arbitrary path or replay support is added. Capacity matches8192 package files plus2 generated configs. All42 targeted combined checks pass, covering real temporary file first-install, upgrade, both rollbacks and UNKNOWN maintenance retention after blob tampering. SCM/ACL are isolated substitutes, not Windows installation acceptance.

中文：干净固定候选tests/实际848项，37FAIL/17ERROR与同日干净ec45401固定结果ID一致，无新增，不是全绿；固定基线原始结果路径及SHA256见REGRESSION_COMPARISON.json，没有机械重跑未变基线。旧13f989d组合23项4 ERROR已保留说明，不能把修复前失败隐藏为通过。
English: The actual clean fixed tests/ candidate runs848 tests with37 failures/17 errors, matching same-day clean ec45401 fixed result IDs without additions; not fully passing. REGRESSION_COMPARISON.json records the reused fixed baseline path/SHA256; the unchanged baseline is not mechanically rerun. The earlier23-test13f989d combination had4 errors and remains documented rather than rewritten as success.

中文：真实AMD64禁用包5056文件，含固定CPython3.13.12及12个固定wheel。四项包内运行检查通过；最终完整性复核在600秒父进程硬超时后为UNKNOWN，未通过整体验证；另用真实包内CPython验证配置终身写保护、bootstrap参数和实际完整宿主清单容量。回滚4964组件逐文件对应通过，不是现场备份或真实回滚。未安装或启用任何服务，未触发Inventory/Provider/邮件。
English: The actual AMD64 disabled archive contains5056 files, pinned CPython3.13.12 and12 locked wheels. Four packaged runtime checks pass; final integrity revalidation is UNKNOWN after the parent600-second hard timeout. Overall verification has not passed. A separate actual packaged-CPython probe checks lifetime write protection, bootstrap arguments and real complete host-manifest capacity. All4964 rollback components match; this is neither a site backup nor actual rollback. No service was installed/enabled and no Inventory/Provider/email operation was triggered.

安装包 / Install archive: C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-host-69eb188\install.zip
SHA256: 0b9f67081afbf481775c0228591df0f89f41a414457a5530ad69a1862a636f7b
回滚工具 / Rollback tools: C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-host-69eb188\rollback-tools.zip
SHA256: 1c74cd2cddb99624c7dd5b82d18462c42ef730bf11f2ab00ad959044917f2ede
Manifest SHA256: 664361ecd462d29e0f862fabcda6c6e507112bad44c759168bb06d286f3de96e

中文：独立审核PENDING；权威费用/真实终态回执CONTRACT_MISSING；原Worker闭包、真实7877/8791跨登录及Windows安装/开机/Session0/恢复验收未完成。所有最终状态false，BUSINESS_GROWTH=UNKNOWN；allow_install/allow_dispatch/allow_cancel_dispatch/SMTP=false。没有新的需用户决定的内部命名事项。整轮无平台硬超时字段，不宣称强制45分钟；包核验子进程600秒硬时限。
English: Independent review PENDING; authoritative charges/real terminal receipts CONTRACT_MISSING. Original Worker closure, real7877/8791 across logins and Windows installation/boot/Session0/recovery acceptance remain incomplete. All final states false; BUSINESS_GROWTH UNKNOWN and all four safety gates false. No internal-naming decision is required from the user. No platform whole-turn hard-timeout field is available; a forced45-minute limit is not claimed. The package-verification subprocess has a600-second hard limit.

开发下一动作 / Next development action:
将批准Provider路径/摘要对接入原Owner控制的ProcessBackend/业务Worker启动；保留isolated_offline与生产门禁关闭，权威结算仍CONTRACT_MISSING。
Connect the approved Provider reference pair through the original owner-controlled ProcessBackend/Worker launch, retaining isolated_offline and closed production gates; authoritative settlement remains CONTRACT_MISSING.

中文：源码差异检查通过；原始回归日志7处测试输出尾空格按原样保留，包含原始日志的git diff --check因此报告空格警告；未修改原始测试输出。最终核验父驱动exit1并输出EXTRACTED_CHECK_TIMEOUT_UNKNOWN，详见VERIFICATION_TERMINATION.json，已确认无遗留核验进程。
English: Source diff checks pass. Seven trailing-space warnings in the raw regression output are preserved; git diff --check including that raw log therefore reports whitespace warnings. Raw test output was not rewritten. The final verification parent exits1 with EXTRACTED_CHECK_TIMEOUT_UNKNOWN; see VERIFICATION_TERMINATION.json. No verifier process remains.
