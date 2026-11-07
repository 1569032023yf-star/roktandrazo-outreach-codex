# U1 standalone bootstrap integration / 独立宿主引导器落地

Task:rokt-razo-20261107T090934Z; start:2026-11-07T17:09:51.3042366+08:00; checkpoint:2026-11-07T09:26:09.305779+00:00
D worktree:D:\CODEX\roktandrazo-workspace\u1-bootstrap-read-20261107; branch:codex/u1-bootstrap-read-20261107
Base:f9d3a27551f7d559b2d239b5a86acc1fd6d393a2; fixed source:afbf24f263e42304d3d73f90e564e3eb48692154

中文：发现真正服务入口仍保留每个小文件按256MiB上限读取及平方级路径碰撞扫描，上一版ReleaseStore修复并未覆盖独立引导器。本轮直接修复该实际启动链：按打开句柄大小加1读取，拒绝超限、硬链接和大小变化；完整组件前缀集合检查替代成对扫描，保留大小写/文件目录碰撞拒绝。没有绕过摘要、路径或UNKNOWN门禁。
English: The standalone service entry still allocated against the256MiB ceiling and scanned path pairs; the previous ReleaseStore fix did not cover it. Fixed the real bootstrap with opened-handle-sized reads plus one byte, rejecting oversize, hard links and size changes. Complete component-prefix checks replace pair scanning while retaining case/file-directory collision rejection. Digest/path/UNKNOWN gates remain intact.

中文：新增实际交付探针，使用包内隔离CPython、包内service/u1_bootstrap.py，在临时发布存储中暂存完整5058文件包、激活临时指针并调用真实resolve_release；不启动服务或业务。最终包真实引导解析3.373601秒。6731字节文件64次可比读取：基线4.186745秒，新版0.016973秒。最终固定源码27项组合通过，12.904秒；测试命令见RESULT.json，受控子进程180秒。未执行/继承旧833全量。
English: Added an actual packaged-bootstrap probe using bundled isolated CPython and service/u1_bootstrap.py against a temporary5058-file release store and fixture pointer; no service/business start. Final packaged resolve_release took3.373601s.64 reads of the same6731-byte file: baseline4.186745s, candidate0.016973s. Final fixed-source27 combined tests passed in12.904s under180s. Historical full-suite results were not inherited or rerun mechanically.

中文：首次新探针失败为WINDOWS_TARGET_PATH_TOO_LONG，失败报告完整保留；修正临时目录为D盘工作区短随机路径，未放宽260/248长度合同。短路径重试成功后重新固定源码并重建全部最终归档。最终完整提取验收VERIFIED/0，受控600秒，实际116.491492秒，五项探针全部通过，首次/最终摘要与输入pin复核均完成。5058文件逐项摘要、回滚4960宿主组件字节一致。首次失败包不作为最终验收。
English: Initial probe failed with WINDOWS_TARGET_PATH_TOO_LONG; retained the complete failure report. Moved only the temporary fixture to a short random D-workspace path, keeping260/248 path gates. After successful retry, fixed the final source and rebuilt both archives. Final extracted verification VERIFIED/0 in116.491492s under600s: all five probes plus initial/final integrity and pin revalidation completed.5058 file hashes and4960 rollback host components match. Initial failed artifact is not the final acceptance candidate.

Install SHA256:c242fab051e85f0c03645a673b87c1b68f74f22fa1fb60bef527318187c12157
Rollback SHA256:520afab37ce563a618808307874e24b1429230ca7d65490c92c27c8c91adc86b
Manifest SHA256:9251efd8bed766f828f9b427d1b6830a71c13f9453efba366d925a2e8e5fcd66
Runtime manifest SHA256:5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e

中文：独审PENDING，不以自检替代。全业务导入闭包、完整业务启动参数、正式Provider费用/终态回执、安装、回滚执行、注销/重启及常驻仍未验收。CONTRACT_MISSING不伪造费用。回滚包是工具不是现场DB备份。没有安装、服务启用、生产DB写入、Inventory触发、邮件或SerpAPI启用。
English: Independent review PENDING. Full business imports/startup arguments, formal Provider billing/terminal receipts, installation, rollback execution, reboot/login and residency remain unaccepted. No fabricated CONTRACT_MISSING amounts. Rollback archive is tooling, not site-state backup. No installation, service enablement, production DB writes, Inventory trigger, mail or SerpAPI enablement.

中文：实际D目录、C Junction、Git远端/主线03c2ec44e1ca4d8b1b8d10841756ded13380f571、协调a823c9c807565ad7087af1da1078736e0ab406d2已核实。canonical本地可读、U1 pending；跨聊天共同入口尚未证明，因此保留主树及canonical不写，只更新明确标识的隔离投影。主树规范要求的CURRENT_STATUS.md/FILE_MANIFEST.md在本隔离源码不存在，未执行任何live操作。仅一条重型线；合作本机锁及受控子进程期限，不宣称全局锁或整个聊天硬超时。正常常驻Python34968未触碰。
English: D directory/C Junction and current Git refs verified. Local canonical queue readable with U1 pending; cross-chat common-entry adoption remains unproven, so main/canonical stay untouched and only the labeled isolated projection changes. CURRENT_STATUS.md/FILE_MANIFEST.md absent from this isolated source; no live action performed. One heavy line; cooperative local locks and bounded children only, no global-lock/chat-wide timeout claim. Existing Python34968 left untouched.

下一步 / Next: Finish remaining business startup argument/import closure; independent review of cumulative fixed source and archives; prove shared-entry adoption before main integration.
DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; SerpAPI disabled.
