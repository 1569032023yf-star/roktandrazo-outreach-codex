# 时钟回拨凭据围栏 / Credential fence after clock rollback

中文：2026-10-30 20:59周期从真实本地/远端b26c6060dc2fc792f3a44b03e9f0c8d7bd34da71恢复。固定源码de39078e6b0c990c451e345467e57ec8407311ab修复过期或不可信时钟恢复后凭据可能再次可用的问题。每个HTTP工厂在内存中共享最后有效时钟与不可逆失效标记，并以互斥锁保护；发现回拨、过期、非法时钟或时钟异常后，该工厂全部后续请求拒绝且不访问后端。相等时间允许，不因普通同秒请求失效。HEAD和原有只读门禁保持。

English: Cycle20:59 restored from actual local/remote b26c6060dc2fc792f3a44b03e9f0c8d7bd34da71. Source de39078e6b0c990c451e345467e57ec8407311ab closes credential revival after expiry or recovery from an untrustworthy clock. A mutex protects a factory-shared last valid time and irreversible invalidation flag. Rollback, expiry, invalid time or clock failure permanently rejects subsequent requests from that factory before backend access. Equal timestamps remain valid. Existing HEAD and read-only gates remain intact.

中文：新增3项真实临时回环HTTP测试：成功读取后时钟回拨再前进、过期后回拨、时钟异常后恢复，均确认后端不再被调用。47项定向组合通过9.020秒；12份固定源码Git blob/SHA256及临时目录隔离导入见SOURCE_MANIFEST.json。独立Reviewer未执行，本增量PENDING。本轮按局部认证状态风险执行组合，不扩用旧833回归、不主张全量无新增回归。测试不是生产身份或无人登录验收。

English: Three new real ephemeral-loopback HTTP tests cover rollback after a successful read, rollback after expiry, and recovery after a clock exception; all verify no further backend calls.47 selected combined tests pass in9.020 seconds. Twelve pinned Git blob/SHA256 entries and isolated temporary-directory import are recorded in SOURCE_MANIFEST.json. Independent review remains PENDING. Risk-scoped combination does not inherit the older833 comparison or establish full-suite no-new-regression. Tests do not establish production identity or unattended acceptance.

中文：围栏只在单工厂生命周期内有效，进程重启/新工厂不继承历史时间；正式凭据签发、轮换、跨进程撤销和独立信任根仍待合同与实现，不以本改动关闭生产认证门禁。首次观察前的时钟回拨无法检测。未绑定8791/SCM或新生产包。下一步先对固定HTTP候选独审，继续正式凭据生命周期及只读backend；并沿57bccd47限定设计补持久安装日志、OS适配层和维护租约校验。当前无可用独立Reviewer，不伪造PASS。

English: The fence lasts only for a handler factory; process restart/new construction does not inherit clock history. Formal issuance, rotation, cross-process revocation and independent trust roots remain outstanding. Rollback before the first observation cannot be detected. This does not close production authentication gates or integrate8791/SCM/new production packages. Next: independent review of the pinned HTTP candidate, formal credential lifecycle/read-only backend, and durable installation journaling/OS adapter/maintenance-lease enforcement following the scoped57bccd47 design. No independent reviewer result is fabricated.

中文：WorkBuddy远端main仍54b79153adf8b8d6df1349e5ea78751bf244f24e，既有Issue2消费回执6520177729沿用，不重复发布。没有新增采样，8791 DOWN及7877单启动反向样本沿用原采样时间，不冒称当前探测；无人登录未通过，SAFE及增长UNKNOWN。保留原未提交证据目录和独立工作树他人文件。没有改生产DB、SMTP、调度、服务、ACL、代理，没有重启或派发。

English: WorkBuddy remote main remains54b79153adf8b8d6df1349e5ea78751bf244f24e. Preserve existing Issue2 receipt6520177729 without duplication. No new production sample: bridge DOWN and the7877 negative startup sample retain their original timestamps rather than becoming fresh probes. Unattended acceptance remains unproven; SAFE/growth UNKNOWN. Preserve the existing untracked evidence directory and others' independent-worktree files. No production database, SMTP, scheduler, service, ACL or proxy changes, restarts or dispatch occurred.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN; allow_dispatch=false; allow_cancel_dispatch=false.

本轮平台未提供整轮硬时限接口；未声称已设置。 / No whole-turn hard-timeout interface was available; none is claimed.
