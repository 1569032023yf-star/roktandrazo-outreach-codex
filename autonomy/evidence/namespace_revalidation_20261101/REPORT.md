# 命名空间复核接合 / Namespace revalidation integration

实际开始 / Actual start: 2026-11-01T13:41:40.3376939+08:00; recorded: 2026-11-01T05:44:04.759662+00:00.
恢复HEAD / Restored local and remote HEAD: ab009d1d3896b41dd64b1fe462c97dc9b29ad6c6.
固定源码 / Pinned source: b642f595c7c97904556126df0e5c2b2d8427295c.

本轮将名字到持有对象ID的检查接入SourceIdentityGuard.revalidate，hash前后各核对一次普通文件identity(volume/fileID/size)，额外句柄只READ_ATTRIBUTES/共享7/OPEN_REPARSE，不改变保留文件句柄的默认SHARE_READ策略。名字检查关闭失败时保留句柄供明确清理并禁用guard；不隐藏错误，不授予重试/安装权限。
This cycle joins named-to-retained object checks into SourceIdentityGuard.revalidate before and after hashing, comparing ordinary-file volume/fileID/size. Extra handles request READ_ATTRIBUTES/share7/OPEN_REPARSE without changing retained-file SHARE_READ. Failed named-handle close retains the handle for explicit cleanup and deactivates the guard; errors are not hidden and no retry/install authority is granted.

新增3项实际Windows测试：hash读取后同内容替换被第二次检查拒绝；返回后替换在下一次检查拒绝且旧快照namespace_immutable_verified=false；关闭失败句柄被保留、guard不可复用且显式清理成功。旧隔离实验更新：不再预期整个revalidate接受替换，保留hash本身仍等于候选但复核拒绝。初次测试28项含import进来的重复TestCase，已改module import，最终定向24项0.492s、组合101项5.687s，全通过；无重复计数。
Three new actual Windows tests cover equal-byte substitution after hashing rejected by the second check; post-return replacement rejected on the next check while the old snapshot keeps namespace_immutable_verified=false; failed close retained with inactive guard and explicit successful cleanup. The earlier experiment now expects revalidate to reject replacement, while the retained hash itself still matches. Initial28-test run included a duplicate imported TestCase; changed to module import. Final24 targeted tests pass0.492s and101 combined pass5.687s, without duplicate counting.

测试由subprocess.run(timeout=120)有界运行，命令/输出见TEST_OUTPUT.txt。本次改动仅离线源guard及其直接发布/日志/兼容依赖，执行这些组合测试；未运行833可比全量，不继承旧全量PASS或NO_NEW_REGRESSION。作者自检通过不等于独立审核，当前固定源码Reviewer=PENDING；旧d7d424c1/079792aa独审仅原范围。
Tests run under subprocess.run(timeout=120); commands/output in TEST_OUTPUT.txt. The change is limited to the offline source guard and direct publication/journal/compatibility dependencies covered by the combined suite. Comparable833 regression not run or inherited; no full-suite/NO_NEW_REGRESSION claim. Author self-check is not independent review: current pinned source review PENDING; older d7d424c1/079792aa reviews retain original scope.

该修复只加强检查时点：名字检查返回后的替换窗口仍存在，未实现租约或ACL保护；不可把两次检查当原子事务/不可变证明。目录持源成功发布仍WinError5。正式Inventory维护租约、Windows可信适配、已有可写映射、掉电、成功后丢回执/突然退出、backend、新文件/删除回滚仍未验收；UNKNOWN不可重放。
This strengthens observation-time validation only: replacement after named readback remains possible; no lease or ACL protection is implemented. Two checks are not an atomic transaction or immutability proof. Successful held-source directory publication remains WinError5-blocked. Formal Inventory lease, trusted Windows adapter, existing writable mappings, power loss, post-success lost receipts/exit, backend and new-file/deletion rollback remain unaccepted; UNKNOWN cannot replay.

WorkBuddy main实际ls-remote仍3033463370e7adf62943e642632955c74394bc7c，无新提交，不重复Issue2回执6546897497。既有SAFE69/69，严格24h/7d增长UNKNOWN；七firing五run两未执行，零漏跑UNKNOWN；Lake20/20 web pending完成5/9、Ithaca冲突未解；8791历史session UP/bootfalse、无人登录持久性未过，7877非交互出口UNKNOWN。历史采样不证明当前计划执行或在线。
Actual WorkBuddy main ls-remote remains3033463370e7adf62943e642632955c74394bc7c, no new commit; do not repeat Issue2 receipt6546897497. Existing SAFE69/69, strict24h/7d growth UNKNOWN; seven firings/five runs/two nonexecutions, zero misses UNKNOWN; Lake20/20 web pending5/9, Ithaca unresolved;8791 historical session UP/bootfalse without unattended persistence acceptance,7877 noninteractive egress UNKNOWN. Historical samples do not establish current health/scheduled outcomes.

下一步 / Next: 继续离线受限命名空间/租约依赖合同及替换窗口故障注入；固定源码独审PENDING，成功持源目录发布仍错误5阻塞。
Continue offline constrained-namespace/lease-dependency contracts and replacement-window fault injection; pinned review PENDING and successful held-source directory publication still blocked by error5.

启动已核实主/宿主树、运行进程、recovery guard、代理变量名、可读附件及canonical本地队列；保留原未跟踪取消证据、宿主候选和creator bridge9836，不处理其他codex进程。本轮独有锁结束核对后释放；recovery guard保留。会话级45分钟硬限制接口不可用，不新建系统任务，测试超时120s且本轮时限内退出。根CURRENT_STATUS/FILE_MANIFEST历史缺失不影响离线验证，不进行live send。
Startup checked main/host trees, processes, recovery guard, proxy names, readable attachment and local canonical queue; preserve untracked cancellation evidence/host candidates and creator bridge9836 without interfering with other Codex processes. Release only verified cycle-owned lock, retaining recovery guard. No session-level45minute hard-limit interface available; no system task created, tests bounded120s and cycle completed within limit. Historically absent root CURRENT_STATUS/FILE_MANIFEST do not authorize live sending.

交付清单：三个源码/测试文件及本目录证据、canonical投影、U1 checkpoint。离线回滚用git revert固定源码，保留journal和账本，不执行生产备份/回滚。未访问生产数据库/HTTP/SMTP，无服务/计划任务/ACL/权限/代理变更、采集或部署。
Delivery: three pinned source/test files, evidence directory, canonical projection and U1 checkpoint. Offline rollback uses git revert of the source pin while preserving journals/ledgers; no production backup/rollback. No production DB/HTTP/SMTP access, service/task/ACL/privilege/proxy mutation, collection or deployment.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN; allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.
