# U1 manifest validation / 清单校验实际修复

Task: rokt-razo-20261107T030728Z; start: 2026-11-07T11:07:36.9927340+08:00
Worktree: D:\CODEX\roktandrazo-workspace\u1-manifest-collision-20261107
Branch: codex/u1-manifest-collision-20261107; base:7c0921e7a839202909ebd726c43a8ae5857a3730; fixed source:6acaee48e045fa735862142637f0182ecf5b128e

修复：ReleaseStore清单命名空间校验从全部文件两两比较改为大小写折叠集合及完整目录分量前缀查询，保留正反插入顺序、大小写碰撞和文件/目录碰撞拒绝。未改变路径合法性、摘要、硬链接或reparse检查。正式验收器在解压、首次完整性、宿主固定、输入复核及最终完整性前持久化具体阶段，成功时清空活动阶段；外层强制结束后不再只能看到空活动检查。
Implemented: replace all-pairs manifest namespace comparisons with case-folded names and complete component-prefix membership. Preserve order-independent case/file-directory collision rejection and all existing path/digest/link checks. Persist verification stages before extraction, initial integrity, host pins, pin revalidation and final integrity; clear the active stage on success.

验证：受控180秒子进程内21项通过，173.459秒；另60秒子进程内6项通过，0.313秒，其中2项重复覆盖，合计25项不同测试。覆盖最大8192文件、前缀相邻但不冲突、大小写及正反顺序、中断保存，以及既有发布生命周期和合同测试。一次重叠启动被WORKTREE_ALREADY_IN_USE拒绝，未执行；等待前一验证结束后才重跑第二组。验证源码内容与固定源码一致。
Validation:21 tests passed in173.459s under180s;6 passed in0.313s under60s (2 overlap,25 distinct tests). An overlapping invocation was refused by WORKTREE_ALREADY_IN_USE before execution; the second suite ran only after the first finished. Tested code matches fixed source.

使用上一轮真实安装包5058文件清单比较：基线1.6402904秒，候选0.0407793秒。此证据仅说明清单解析优化，不能证明600秒提取验收超时已解决。上一轮四探针后无阶段记录，无法区分输入句柄复核、关闭及最终文件复核；此前笼统“最终复核”应理解为未定位的探针后完整性阶段，不是已证实根因。
On the actual prior5058-file manifest, baseline1.6402904s versus candidate0.0407793s. This proves parser improvement only; it does not resolve or explain the prior600s timeout. The old report lacked post-probe stage markers, so pin revalidation/closure/final file scan were not distinguished. The precise timeout location remains UNKNOWN.

未新建或重新验收安装包；7c0921e发布的旧包不包含本轮新源码，不能继承验收。独审PENDING。下一步按新增阶段执行新固定候选的离线验收，定位剩余耗时并修复，随后独审/新包。正式费用终态CONTRACT_MISSING不变。
No new package or inherited acceptance. The previous package does not contain this source. Independent review PENDING. Next: stage-aware offline verification of a newly fixed candidate to locate remaining costs, then review/new artifacts. Formal billing/terminal contracts remain missing.

主树/远端03c2ec44e1ca4d8b1b8d10841756ded13380f571未变；本地canonical已读取，U1主任务pending。本轮仅隔离投影更新，跨聊天共同互斥接入未验证，未冒险并发写主树。D路径与C Junction已核实。既有协调锁只证明本机合作进程；无平台聊天级硬限制声明。
Main unchanged; canonical read, U1 task pending. Only isolated projection updated because shared cross-chat entrypoint adoption is unverified. D directory and C Junction checked. Cooperative local locks and child deadlines do not prove global or whole-chat enforcement.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; SerpAPI disabled.
