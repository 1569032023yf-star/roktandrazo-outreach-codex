# U1 开发协调候选 / U1 Development Coordination Candidate

中文：基于 03c2ec44e1ca4d8b1b8d10841756ded13380f571 在 C 盘独立工作树开发本机 Windows 协调候选。代码提供两个内核字节锁槽、唯一 UUID 记录、同工作目录冲突检查、独立 Git 短锁、进程异常后锁释放与遗留记录标记，以及使用现有 Job Object 的有界子进程运行。开发锁与生产业务恢复锁分离。

English: A Windows-local development coordination candidate was developed in an isolated C: worktree from 03c2ec44e1ca4d8b1b8d10841756ded13380f571. It provides two kernel byte-lock slots, unique UUID records, same-worktree conflict checks, a separate short Git lock, process-death lock release with abandoned-record marking, and bounded child execution using the existing Job Object. It is separate from production recovery locks.

中文：`python -B -m unittest test_dev_cycle -v` 四项通过，包含多个真实进程竞争、两槽满载、重复目录与重复 run_id、强制结束后恢复、Git 锁竞争和一秒超时。该候选未完成独立审查，尚未部署到总控；仅适用于共同使用同一个本机目录及同一入口的合作进程。未验证跨环境文件系统可见性、目录或锁文件遭替换的防护、所有聊天接入、进程树在宿主崩溃时的完整行为，也未证明整个聊天轮次被强制限制为45分钟。不能据此宣称全局并发或自动任务已强制受控。

English: `python -B -m unittest test_dev_cycle -v` passed four tests using actual processes: two-slot contention, duplicate directory and run ID rejection, recovery after forced exit, Git lock contention and one-second timeout. Independent review is pending and the candidate is not deployed to the controller. Its scope is cooperating processes sharing one local directory and entrypoint. Cross-environment visibility, resistance to lock-file/directory replacement, universal chat adoption, full process-tree behavior on host crash, and a hard 45-minute limit on the entire chat turn remain unverified. No global or scheduler enforcement is claimed.

中文：正式 Provider 费用和终态合同、业务导入闭包、完整包、Windows 服务验收仍未完成。未采集、生产数据库写入、安装、派发、发邮件或修改配额。下一步对固定候选独审并补齐锁文件身份、崩溃进程树、跨进程实际部署入口和总控集成，再推进 P0 Worker。敏感信息检查：无凭据或客户数据。DEVELOPMENT_COMPLETE=false，RELEASE_READY=false，PRODUCTION_DEPLOYED=false，PRODUCTION_ACCEPTED=false。

English: Formal Provider billing and terminal contracts, business import closure, complete package and Windows service acceptance remain open. No collection, production database write, install, dispatch, email or quota change was performed. Next independently review the pinned candidate, strengthen lock-file identity, crash-tree handling, actual cross-process integration and controller adoption, then advance the P0 Worker. Sensitive data check: no credentials or customer data. DEVELOPMENT_COMPLETE=false, RELEASE_READY=false, PRODUCTION_DEPLOYED=false, PRODUCTION_ACCEPTED=false.
