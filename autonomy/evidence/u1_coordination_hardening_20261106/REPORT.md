# U1 协调修复 / Coordination hardening

中文：任务 rokt-razo-20261106T090442Z；实际开始 2026-11-06T17:05:02+08:00，工程检查完成 2026-11-06T09:15:50.342662+00:00。权威目录 D:\CODEX\roktandrazo-workspace；本轮仅修改独立工作树 u1-coordination-hardening-20261106，分支 codex/u1-coordination-hardening-20261106。Git 2.54.0.windows.1。已核验旧 C 目录为指向权威 D 目录的 Junction，未修改备份。主树/远端 03c2ec44e1ca4d8b1b8d10841756ded13380f571；协调远端候选 a823c9c807565ad7087af1da1078736e0ab406d2。固定修复源码 688beeb67b089a8bd0545c9b9fbd5818f8b36870。

English: Task rokt-razo-20261106T090442Z started at 2026-11-06T17:05:02+08:00; engineering checks ended at 2026-11-06T09:15:50.342662+00:00. Only the isolated D: worktree/branch above was changed. Git is 2.54.0.windows.1. The old C: path was verified as a Junction to the authoritative D: workspace; backups were untouched. Main/remote and candidate/source revisions are pinned above.

中文：对候选实际审核发现锁文件和祖先可替换、硬链接元数据可写入其他文件、异常/超时错误标为完成，以及终结记录失败可能漏释放槽。复用安装器 InstallInputPins 固定普通目录和文件身份，拒绝 reparse/硬链接；元数据通过固定句柄写入并 fsync；失败记录 FAILED，无法确认树清理记录 STOP_AND_PRESERVE 并阻止自动复用；槽释放在独立 finally。CLI 使用既有 Job Object，不新增调度器。目录必须预先存在；没有更改 ACL 或服务。

English: Candidate review found replaceable lock identities/ancestors, hardlinked metadata write exposure, false completion on failures/timeouts and potential slot leaks on finalization errors. The fix reuses installer identity pins, rejects reparse points/hardlinks, writes metadata through pinned handles with fsync, records failures and preserves unverified cleanup, with unconditional slot release. The CLI reuses the existing Job Object and requires a pre-existing ordinary directory; no scheduler, ACL or service change was introduced.

中文：固定源码通过 32 项组合：python -X utf8 -B -m unittest test_dev_cycle test_install_inputs autonomy.test_process_job -v。其中协调 11 项；包含真实 Git 短锁命令、两槽竞争、锁/祖先替换拒绝、Junction/硬链接拒绝、1 秒超时、已启动父子进程树在监督进程被杀后退出。tests.txt 保存原始输出；controlled-run.json 保存受控执行回执，run_id=bdb476de-a572-42d2-ba29-b93d678a6c10。测试调用超时 300 秒，CLI 最大 2700 秒；不是整个聊天的硬停止。本轮前段检查/编辑不在该执行槽内，不声称全轮强制受控。

English: All 32 combined tests passed at the fixed source, including 11 coordination tests exercising actual Git, multiprocess contention, identity/link rejection, a one-second deadline and started child/grandchild termination after supervisor death. Raw output and the controlled-run receipt are retained. The test child deadline was 300 seconds, with CLI maximum 2700; this does not hard-stop the chat, and initial inspection/editing was outside this slot.

中文：新修复独审 PENDING。仅证明同机合作进程；尚未证明所有聊天接入、跨环境共享或非合作 Git 被阻断。进程创建到加入 Job 的挂起窗口崩溃仍未验收。JSON 撕裂/损坏需保留证据，不自动修复；复用安装器内部身份辅助函数有 API 耦合。没有新完整安装包/新全量回归，不继承旧包验收。共同协议尚未全面采用，因此不合并主树，不写主树 canonical queue/checkpoint，避免与其他聊天争写；本分支只更新显式状态投影，不能冒充 canonical。

English: Independent review of the fix is PENDING. Evidence covers local cooperating processes, not universal chat adoption, cross-environment sharing or exclusion of uncooperative Git. Crash during the suspended creation-to-Job assignment window remains unaccepted. Torn/corrupt JSON must be preserved, with no automatic repair; private installer identity helpers create API coupling. No new complete package/full regression or inherited package acceptance is claimed. Without universal protocol adoption, main/canonical files remain untouched; branch state is explicitly a projection only.

中文：唯一下一步：固定 688beeb67b089a8bd0545c9b9fbd5818f8b36870 独审并验证创建到 Job 绑定窗口及多聊天共同入口，再在共同互斥下集成主线和同步 canonical；随后继续 Provider/Worker 离线闭包。正式费用/终态合同保持 CONTRACT_MISSING。全部生产门禁 false；无安装、采集、邮件、生产写入或新增 Inventory。

English: Next independently review the fixed revision and validate the creation-to-Job window and shared chat entrypoint, then integrate under verified mutual exclusion and synchronize canonical state. Continue offline Provider/Worker closure afterward. Formal billing/terminal contracts remain CONTRACT_MISSING. All production gates remain false; no installation, collection, email, production writes or additional Inventory.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
