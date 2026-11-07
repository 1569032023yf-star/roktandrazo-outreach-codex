# U1 bounded artifact reads / 有界文件读取与实际包验证

Task:rokt-razo-20261107T061201Z; start:2026-11-07T14:12:10.1648777+08:00
D worktree:D:\CODEX\roktandrazo-workspace\u1-bounded-read-20261107; branch:codex/u1-bounded-read-20261107
Base:419a511b68c916c3282dc11927b02a47a5124a91; fixed source:f5073c523c4d79abca82210d53b8ddae7510f330

本轮先实际构建419a511完整运行时包并定位：600秒超时精确停在final_integrity，四项探针已通过；原始RUNNING报告与执行器FAILED/TIMED_OUT/124均保留。随后修复ReleaseStore.read_file按256MiB上限读取每个小文件导致重复大分配的问题：改按已打开句柄fstat大小读取并多读1字节，拒绝超限、硬链接及大小变化。路径/reparse/摘要检查保留。没有缩短检查列表或跳过最终复核。
First built the419a511 runtime package and reproduced600s timeout at final_integrity after four passing probes. Raw RUNNING report and controlled TIMED_OUT/124 receipt retained. Fixed read_file allocating against the256MiB admission ceiling for each small artifact: size reads from the opened handle plus one byte, rejecting oversize, hard links and size changes. Path/reparse/digest and final checks remain enabled.

实测同一本地19324字节文件64次：基线4.2272467秒，候选0.0106229秒。27项定向与组合测试全部通过，76.015秒（120秒受控子进程）；命令python -B -m unittest test_release_store test_large_runtime_release test_release_contract test_delivery_verification。没有重复未变化源码的旧833全量，也不继承其结果；新固定候选完整全量仍未执行。
Same19324-byte local file,64 reads: baseline4.2272467s, candidate0.0106229s. All27 targeted/combined tests passed in76.015s under120s. No inherited historical full-suite result; broad new-candidate regression has not been run.

实际交付：新固定源码、真实AMD64 CPython与业务依赖完整成对归档；宿主准备与归档最终输入复核均成功。新包提取完整验收FINISHED/0、VERIFIED，44.776278秒；包括首次和最终完整性、固定输入复核、业务入口导入/隔离子进程、pip check、原生运行时清单与回环401/200认证。5058文件归档摘要逐项通过，回滚4960宿主组件字节对应通过。
Delivered new fixed-source archives with real pinned AMD64 CPython/business dependencies. Host preparation and final build input checks succeeded. Fresh extracted verification FINISHED/0, VERIFIED in44.776278s including initial/final integrity, pin revalidation and all four probes.5058 archive digests and4960 rollback host components matched exactly.

Install SHA256:d2ec9f91a223b3aba25b8f412c1efe1c4d5ccdc9c590bd56674b67b8ac89c8ab
Rollback SHA256:24ef1313eab3861bc3c85804b3fa7138e72176c35380deb64037b5bf43654821
Manifest SHA256:29e0e49e2ab5b3e6621f43ef570e837a02c02f1642d74d3149b853a01ad96892
Runtime manifest SHA256:5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e

边界：这证明离线包验证，不证明正式Provider、业务全导入闭包、启动参数、安装、回滚执行、注销/重启或Windows常驻验收。独审PENDING；正式费用及终态CONTRACT_MISSING。回滚包是工具，不是生产DB/现场状态备份。未安装或启用服务，未触发Inventory，未写生产DB或发信。
Scope: offline artifact verification only; not formal Provider/full business import closure/bootstrap/installation/rollback/reboot/residency acceptance. Review PENDING and formal billing/terminal contracts missing. Rollback archive is tooling, not production-state backup. No installation, production collection, DB writes or mail.

主树/远端03c2ec44e1ca4d8b1b8d10841756ded13380f571及canonical未改，已读取本地U1任务pending；隔离投影已更新。跨聊天共同入口接入仍未证明，不并发改主树。C Junction与实际D目录核实；仅本机合作锁及受控子进程期限，无全聊天硬截停声明。复用既有环境证据，未重复索要。仅两条工作线（固定包复现与隔离读取修复），前者已终止保存。
Main/canonical unchanged, local U1 pending task read; isolated projection updated. Cross-chat common-entry adoption unverified, so no main-tree concurrent writes. D/Junction checked; cooperative local locks and controlled children only. Existing environment evidence reused; at most two work lines.

下一步：独立审核固定f5073c523c4d79abca82210d53b8ddae7510f330及安装/回滚归档；推进真实业务启动参数/导入闭包尚缺部分。未经明确授权保持禁止安装和派发。
Next: independent review of fixed source and paired artifacts; finish remaining business startup/import closure. Installation and dispatch stay disabled pending explicit authorization.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; SerpAPI disabled.
