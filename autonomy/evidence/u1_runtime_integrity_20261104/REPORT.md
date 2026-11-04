# U1 完整运行时启动前完整性 / Full-runtime prelaunch integrity

## 固定源码与变化 / Pinned source and change
中文：最终代码05783f2c560825e0b5095b99afdc6b9b86f47955；前一候选02798cf保留。新增rokt.u1-runtime-content.v1清单，rokt.u1-provision-plan.v2和rokt.u1-supervisor.v2绑定其独立摘要。Publisher正式安装入口在既有批准记录的runtime_plan_sha256内核对该清单并固定所有内容；未改变六项候选批准字段或Inventory所有权。C#服务在CreateProcess之前核验每个文件，并持有文件和目录句柄直到子进程清理；拒绝硬链接、reparse、路径越界、大小/数量超限和未列出的文件。旧v1入口仅保留兼容，不视为完整运行时验收。门禁全false。
English: Final code05783f2c560825e0b5095b99afdc6b9b86f47955; prior02798cf evidence is retained. A rokt.u1-runtime-content.v1 manifest is bound by rokt.u1-provision-plan.v2 and rokt.u1-supervisor.v2 with an independent digest. The existing Publisher installation entry verifies and pins that tree within the already-approved runtime_plan_sha256. The six approval fields and Inventory ownership are unchanged. C# validates all files before CreateProcess and retains file/directory handles until child cleanup. Hardlinks, reparse paths, traversal, count/size excess and unlisted files are rejected. Legacyv1 remains compatible, without complete-runtime acceptance. Every gate stays false.

## 测试证据 / Test evidence
中文：最终26项相关定向测试全部通过，见FINAL_TARGETED_OUTPUT.txt；涵盖原安装/配置合同、新v2配置生成、C#与Publisher实际文件校验、标准库/DLL篡改、空文件、合法GMT+0时区名称、未列出.pth、路径越界、大小写冲突、摘要错误及句柄持有期间拒绝写入。此前27项组合中服务子进程测试失败，TARGETED_OUTPUT.txt保留；5a8394d基线独立运行同一服务测试也失败，BASELINE_SERVICE_OUTPUT.txt保留，不能记为通过。该项当前根因未确定，不因新定向测试通过而抹去。
English: All26 final focused tests pass (FINAL_TARGETED_OUTPUT.txt), covering existing install/config contracts, actualv2 config generation, native/Publisher verification, DLL/stdlib tampering, empty files, legitimateGMT+0 paths, unlisted.pth hooks, traversal, case collisions, wrong hashes and blocked writes while pinned. The earlier27-test group includes a service-child failure (TARGETED_OUTPUT.txt). The same test also fails independently on baseline5a8394d (BASELINE_SERVICE_OUTPUT.txt); it is not counted as passing. Its cause remains unresolved and is not erased by new passing checks.

中文：真实CPython与12个业务wheel的4943文件清单通过最终C#只读校验，stdout=VALID_PINNED_RUNTIME；Publisher实际Windows句柄固定和revalidate均通过。清单SHA256=5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e，见REAL_RUNTIME_FINAL.json和U1_RUNTIME_CONTENT.json。运行时底座仍为32f0246装配资产。02798cf初次实际校验拒绝合法时区加号路径，REAL_RUNTIME_VALIDATION.json保留；修正未剔除标准库/时区数据。最初构建使用系统临时目录遭csc非零及WinError5，改用工作区临时目录后成功，未更改权限策略。以上不是服务启动、安装或真实业务执行证据。
English: Final native read-only validation passes on4943 files from real CPython and12 wheels, returningVALID_PINNED_RUNTIME. Actual Publisher Windows-handle pinning and revalidation also pass. Manifest SHA256=5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e (REAL_RUNTIME_FINAL.json and U1_RUNTIME_CONTENT.json). Runtime assets originate from32f0246 assembly. Initial02798cf rejects legitimate timezone plus paths; REAL_RUNTIME_VALIDATION.json preserves the failure. The fix does not remove stdlib/timezone data. An initial build using system temporary directories hit csc nonzero/WinError5; workspace temporary storage succeeds without policy changes. These checks are not service startup, installation or real business execution evidence.

## 工程包与回归 / Engineering archive and regression
中文：05783f2工程包84文件，安装ZIP=c19797671dfda39687798b435f82ef6351f5515d03b65afcc68457915ae48a90，回滚ZIP=7287bd1c417fe1ac5c67c94660a4ef3654946f36c265422128ab4099a994467a，manifest=1aeeb98b00385d4fabde0ef4fa417755df53cddd730c235fa19f6473b66a1475。包内全部摘要及Python文件与Git原始字节逐一核验。包内新C#和Publisher支持v2外部固定运行时，但完整运行时仍未纳入安装ZIP，因此不能称PACKAGE_COMPLETE。最新Publisher修复6c60dba1是该候选祖先，已包含其源码。独立审核PENDING。
English: The05783f2 engineering archive contains84 files. Install ZIP=c19797671dfda39687798b435f82ef6351f5515d03b65afcc68457915ae48a90; rollback ZIP=7287bd1c417fe1ac5c67c94660a4ef3654946f36c265422128ab4099a994467a; manifest=1aeeb98b00385d4fabde0ef4fa417755df53cddd730c235fa19f6473b66a1475. Every digest and packaged Python Git byte is verified. C#/Publisher support av2 pinned external runtime, but the full runtime is not in the install ZIP: PACKAGE_COMPLETE remains false. Publisher fix6c60dba1 is an ancestor and its code is included. Independent review is PENDING.

中文：5a8394d基线与05783f2候选在两个干净工作树启动同一完整tests/回归；句柄74787、12397运行中，原始进度及输出保存full-baseline/full-candidate，不能用旧837项结果替代本候选。RUNNING_HANDLES.json仅用于定位，不单凭文件判断进程活性。
English: Baseline5a8394d and candidate05783f2 run identical fulltests/ regression from clean worktrees, sessions74787/12397, with raw progress/output in full-baseline/full-candidate. Earlier837-test results do not apply to this candidate. RUNNING_HANDLES.json is a locator, never standalone liveness evidence.

## 未完成项与下一步 / Remaining work and next step
中文：现有文件事务将新旧内容inline/base64写入日志，载荷/备份各16MiB，512文件；完整运行时不能直接套用或仅加大上限。下一步实现固定运行时子树的暂存、提交、补偿和精确所有权回执，纳入原安装维护排他与持久intent；保留原非对称ACL、旧版本和未知现场，不新增Inventory锁。随后绑定Bootstrap及包内runtime路径，验证升级/回滚/进程退出恢复。浏览器驱动启动超时仍未解决，业务动态导入闭包尚未证明。CONTRACT_MISSING只阻塞正式Provider接入；其他离线工程继续。
English: Existing file transactions inline/base64 old/new contents into journals with16MiB payload/backup and512-file limits. The full runtime cannot simply use larger limits. Next: stage, commit and compensate a pinned runtime subtree with exact ownership receipts, using original installation exclusion and durable intent. Preserve accepted asymmetric ACLs, prior versions and unknown state, without a new Inventory lock. Then bind Bootstrap/package runtime paths and verify upgrade/rollback/process-exit recovery. Browser driver-start timeout and full dynamic business import closure remain unresolved. CONTRACT_MISSING blocks formal Provider integration only; independent offline engineering continues.

中文：DEVELOPMENT_COMPLETE、PACKAGE_COMPLETE、PROVIDER_ACCEPTED、WINDOWS_ACCEPTED、RELEASE_READY、PRODUCTION_DEPLOYED、PRODUCTION_ACCEPTED全部false。allow_install、allow_dispatch、allow_cancel_dispatch、smtp_enabled全部false。未安装服务、修改生产ACL/数据库、触发Inventory、进行生产请求、扣费或SMTP。输入和包内未加入真实凭据。
English: DEVELOPMENT_COMPLETE, PACKAGE_COMPLETE, PROVIDER_ACCEPTED, WINDOWS_ACCEPTED, RELEASE_READY, PRODUCTION_DEPLOYED and PRODUCTION_ACCEPTED are allfalse. allow_install, allow_dispatch, allow_cancel_dispatch and smtp_enabled remainfalse. No service install, production ACL/database mutation, Inventory trigger, production request, charge or SMTP action occurred. No real credentials were added to inputs or archives.


## 完整回归收尾 / Full regression closeout

完整回归已结束：候选05783f2与基线均运行842项，均37项失败；候选19项错误，基线18项错误。新增测试初始化被开发子进程保护阻止，完整回归未通过。原始输出已保留，不放宽保护。运行时安装事务待开发，Provider CONTRACT_MISSING，全部门禁及最终验收状态false。

New test initialization is blocked by development subprocess protection; neither protection nor tests are bypassed. Candidate:842/37 failures/19 errors; baseline:842/37 failures/18 errors. NOT ACCEPTED.


## 大运行时事务开发 / Large-runtime transaction development

新增原文件事务磁盘备份模式，17MiB文件安装/回滚、备份篡改拦截、写入后中断且禁止向前重放：3项定向测试通过。固定代码df4327e。原内嵌模式限制保持；磁盘备份模式每侧最多1GiB、单文件256MiB，日志记录摘要和备份目录身份。尚未接入PowerShell安装入口；全CPython事务、独立审核、最新整包与完整回归未完成。

Original file transaction now supports disk-backed payloads. Three focused tests pass:17MiB apply/rollback, blob tamper rejection, and post-effect interruption compensation with no forward replay. Fixed code df4327e. Inline limits remain unchanged; disk-backed mode permits1GiB per side and256MiB per file with digest references and store identity in the journal. PowerShell installer integration, full CPython transaction, independent review, updated package and full regression remain incomplete.


追加结果：df4327e原文件事务14项、0失败1错误（76.059秒）。错误为旧硬链接注入os.link触发WinError5；5a8394d基线单独复现同项同错。新增3项通过不等于全组通过。全组原始输出保留在工具会话74455，未保存原始输出文件。

Additional result:df4327e original file suite ran14 tests,0 failures/1 error in76.059s. Legacy hardlink injection raises WinError5 at os.link; targeted baseline5a8394d reproduces the same error. Three new passing tests do not establish a green full group. Full raw output exists in tool session74455; no raw file was captured.


## 原安装入口接入 / Original installer integration

固定代码8525fb7：原PowerShell安装事务已传递file_sources路径与已批准SHA256；Python接收端逐文件复核后进入原磁盘备份事务。生成配置和安装回执仍随原请求传递，维护授权与补偿顺序未更改。5项Python请求/磁盘事务测试通过；实际PowerShell请求生成块与Python安装/回滚测试通过（不运行服务安装）。完整CPython仍受包清单、发布仓库和Bootstrap容量/路径协议限制，完整运行时安装尚未验收。最新SHA完整回归、独立审核、真实Windows生命周期未完成。

Fixed code8525fb7: original PowerShell installer passes file_sources paths with approved SHA256; Python verifies each file before entering the original disk-backed transaction. Generated configuration and installation receipt remain in the original request; maintenance authority and compensation order are unchanged. Five Python request/disk transaction tests pass; actual PowerShell request construction plus Python apply/rollback passes, without service installation. Complete CPython integration still requires package, release-store and Bootstrap manifest capacity/path contracts. Full-runtime installation is NOT ACCEPTED; full regression for this SHA, independent review and real Windows lifecycle remain incomplete.


兼容检查：4项通过，21.641秒；原始输出INSTALL_REQUEST_COMPAT_OUTPUT.txt。未执行真实服务安装。

Compatibility:4 tests pass in21.641s; raw output INSTALL_REQUEST_COMPAT_OUTPUT.txt. No real service installation performed.


## 大运行时发布清单 / Large-runtime release manifest

固定源码b008663：新增显式rokt.release-manifest.v2，最多8192文件、总1GiB、单文件256MiB；逐文件构建，旧v1仍512文件/128MiB。Bootstrap同步识别v2与规范化清单，允许合法加号路径，保留逐文件哈希及未列文件拒绝。原宿主包及Publisher仍待统一；未生成完整安装包，最新完整回归与独审未完成。

Fixed source b008663: explicit rokt.release-manifest.v2 supports8192 files,1GiB total and256MiB per file with file-at-a-time construction. Legacy v1 retains512 files/128MiB. Bootstrap shares v2 and canonical manifest checks, permits legitimate plus paths, and retains digest/unlisted-file rejection. Host package and Publisher alignment, complete installation archive, full regression and independent review remain pending.


## 宿主v2与完整运行时组包 / Host-v2 runtime assembly

固定源码03eca14：宿主v2组包工具已纳入，固定宿主清单及完整运行时摘要，逐文件复制；Publisher接受显式v2和零字节依赖，允许合法加号路径，仍检查文件摘要与所有权保留路径。b008663发布/Bootstrap及原发布回滚10项通过（182.509秒）；本轮宿主v2组包/Publisher及实际PowerShell请求2项通过（8.779秒）。真实CPython宿主组包运行中，句柄39800。该宿主包尚未含完整应用发布包，运行计划安装路径绑定仍待完成；不标记PACKAGE_COMPLETE。

Fixed source03eca14 adds pinned host-v2 assembly from host/runtime manifests, copying one file at a time. Publisher supports explicit v2, empty dependency files and legitimate plus paths while retaining digest and reserved ownership checks. b008663 release/Bootstrap and original publication rollback:10 tests passed in182.509s. Current host-v2/Publisher and actual PowerShell request:2 tests passed in8.779s. Real CPython host assembly is running under handle39800. This host candidate is not the complete application release; installed runtime-plan path binding remains pending. PACKAGE_COMPLETE remains false.
