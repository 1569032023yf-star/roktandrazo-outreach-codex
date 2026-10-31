# U1 工程与新生产证据消费 / U1 engineering and new production evidence consumption

本轮实际开始2026-11-01 01:33:31.874+08；触发时间2026-10-31T17:33:23.018Z。恢复时本地和远端HEAD均796b9c2cfd941c111be0e82ccf35a0e56c89bcce。保留原未跟踪取消证据与独立宿主工作树，合法recovery guard不删除；未发现另一U1开发进程。本轮未访问生产DB、SMTP或启动Inventory。未配置新的系统任务；当前接口没有会话硬时限控制，采用短时有界命令并在45分钟内结束。

Actual start01:33:31.874+08 on Nov1; heartbeat17:33:23.018Z on Oct31. Local and remote HEAD at recovery both796b9c2cfd941c111be0e82ccf35a0e56c89bcce. Preserve pre-existing untracked cancellation evidence, host worktree and valid recovery guard. No other U1 developer observed. No production DB/SMTP access or Inventory start. No new system task; session hard timeout unavailable, use bounded commands and finish within45 minutes.

## 固定证据 / Pinned evidence

WorkBuddy main固定3033463370e7adf62943e642632955c74394bc7c；七份原始字节Git blob重算、JSON解析通过，声明schema_version1.0；仅声明结构检查，没有外部正式JSONSchema。六份声明payload_sha256全部按既有剥metadata规则重算匹配；operations未提供该字段/producer，不记成hash失败，其sources/fields保留。完整来源、采样和hash见VERIFICATION.json与source原件。

Pinned WorkBuddy main3033463370e7adf62943e642632955c74394bc7c. All seven original Git blobs and JSON parse verify; declared version1.0 only, no external formal JSON Schema. Six declared payload hashes match existing metadata-stripping recipe. Operations provides no payload hash/producer; retain fields/sources, mark absent rather than mismatch. Full provenance/timestamps/hashes in VERIFICATION.json and original source bytes.

| 文件 / File | Git blob SHA |
| --- | --- |
| CITY_STAGE_TRACE.json | `799a78e73e25c8923d46dfd6b05603f1a035888d` |
| INVENTORY_SCHEDULER_RECONCILIATION.json | `ee965af2905c326f5a66901c81c6991f60756c97` |
| PRODUCTION_RUNTIME_LATEST.json | `9932a9c6312ebeb3cb47367f03671811a18ca5aa` |
| PROVIDER_REQUEST_AUDIT_24H.json | `472b5738b6a23687534c455cf97d0b2f6991e797` |
| RELEASE_REGISTRY_SNAPSHOT.json | `432448dac12c578cf70c886f2c8aebf2c34d5863` |
| SAFE_AUTHORITY_SNAPSHOT.json | `40eed0be92629a792ccd07ab0564739c703e1285` |
| WORKBUDDY_LONG_TERM_OPERATIONS.json | `1eac061e8639f6cfe867636716aa11d8a1e5fffb` |

SAFE测量起点10/31 23:43:28，实际两次采样23:49:42及23:55:08，均69；MX正负控制ok/nxdomain，DB quick_check ok。生成23:55:16，Git提交23:55:37（UTC15:55:37），晚21秒，当前证据没有旧11:55晚于11:52的倒置。旧5a290610的时间保留在旧回执，不能改写或传播到新pin。本次消费发生11/1凌晨；快照不是此刻实时健康证明。

SAFE measurement begins23:43:28, actual readings23:49:42 and23:55:08 both69; MX controls ok/nxdomain, DB quick_check ok. Generated23:55:16, committed23:55:37 (+21s; UTC15:55:37). No inverted timing in this pin. Preserve historical5a290610 inversion in its original receipt. Consumption occurs after midnight; snapshot is not current live health.

## 对账与保留 / Reconciliation and reservations

- SAFE69/69确认；自报24h0、7d+13，但reason/unavailable仍明确无同规则基线，且未给baseline快照。h24标记距measured_at25h02m25s，d7标记164h39m53s；严格24h/168h均UNKNOWN。历史62→63→64→63不改写成单调增长，新69也不能证明商业增长。
- SAFE69/69 verified in published samples. Producer reports0/+13, while reason/unavailable deny comparable baseline; baseline snapshots absent. Labelled intervals25h02m25s and164h39m53s are not24/168h. Strict growth and business growth UNKNOWN. Preserve historical62→63→64→63 without monotonic interpretation.
- Inventory原唯一authority automation-1784775229336。七firing中五个与真实completed Inventory按run_id/trigger/stage/窗口一对一匹配；两个executed=false、run_id=null，不当作两次生产执行，原因UNKNOWN。最新真实run d52e84fd与2e419944均target60/actual69；次次firing最大漂移674.95s超过600s。零漏跑UNKNOWN；全局唯一性缺系统任务可见性。下一计划11/1 04:20:57.904+08，尚未发生。
- Canonical Inventory authority unchanged. Seven firings yield five verified runtime joins and two executed=false/null-run receipts, reasons UNKNOWN. New runs d52e84fd/2e419944 both60/69. Max drift674.95s exceeds600s. Zero misses/global uniqueness unproven; next scheduled04:20:57.904+08 has not occurred.
- 两个新run的current_step均可解析为16条真实JSON事件；旧current_step_note/stage_events不可用文案与数据冲突，不能因此声称没有轨迹。runtime running_inventory_now=6不是六个已证活进程；历史post-send错误归因仍保留。
- Both new run current_step fields contain16 parsed events. Stale prose denies logs and contradicts actual JSON. running_inventory_now6 does not prove six live processes; historical post-send attribution remains unresolved.
- Cooperstown正式关闭9/9；operations NEXT_AUTOMATIC_ACTION仍称不会关闭是旧文案，不触发重复patch。Lake Placid20/20，places_matrix_completed_web_pending，completed_at=null，完成检查5/9（四项失败：all_candidates_classified/no_unprocessed_candidates/official_site_recheck/review_recovery），不是正式关闭。Ithaca此次未提供，新证据不能解决原完成冲突。
- Cooperstown closed9/9; stale automatic-action prose is preserved and does not justify another patch. Lake Placid20/20 but web pending, null completion timestamp and5/9 checks; no formal closure. Ithaca absent; earlier completion conflict unresolved.
- Provider修正all_cities_7d city_id=null，承认范围标签修复；48 auditrows、requests47/success46/failed2/timeout2仍缺口径；Lake56是城市累计，不能与7d范围强行相等。Cooperstown24h零请求只限该城。
- Provider all-cities scope label is corrected to null city_id.48 audit rows versus47 requests/46 successes/2 failures/2 timeouts still require definitions. Lake56 cumulative is a different scope. Zero24h Cooperstown calls apply only to that city.
- 8791仅23:55:15会话内UP；boot persistence=false，登录自启REGISTERED_NOT_OBSERVED；跨调用/跨登录/无人登录运行仍未验收。7877非交互真实登出出口UNKNOWN。不以Session0结构、自报crash recovery或健康接口代替持久性。
- 8791 UP only within sampled session; boot persistence false, login startup registered but unobserved. Cross-call/login/logoff acceptance remains unmet;7877 real noninteractive/logged-off egress UNKNOWN. Session0 structure/crash-recovery claim/health endpoint do not substitute.
- SMTP生产自报raw0、来源一致，today0/historical517、unauthorized mail0/write0；这不是Codex独立DB审计。本轮Codex生产访问/写入/邮件均0。DB新hash0f38d4f43645416b6c2b85b838c9cd661a9c0021c8ffd574139ec4cc41a5ba7b，mtime22:03:46，不宣称生产DB全局未变。注册S/U/V/W四项seal=true/tampered=false，仅消费不重apply。
- Producer reports SMTP raw0/agreement, today0/historical517 and unauthorized mail/writes0; not an independent Codex DB audit. This cycle performs zero production DB/SMTP operations. New DB hash/mtime preserved, no global unchanged claim. Four registered S/U/V/W releases sealed/untampered; no reapply.

## 本轮实现 / Implementation

源码d14370286cb66a0e2040018db67dae8ae5b57247在handoff_validation新增纯函数reconcile_safe_growth：必须提供完整可比快照、相同规则和去重method、非bool非负整数、aware时间及精确24/168h才计算差额；不授权派发、不推断商业增长。新增9测试，77组合通过4.593s。未重跑833，旧结果不继承；独立Reviewer未执行，PENDING。

Source d14370286cb66a0e2040018db67dae8ae5b57247 adds pure reconcile_safe_growth: require complete comparable snapshots, identical rules/dedup method, nonboolean nonnegative integer counts, aware timestamps and exact24/168h interval. No dispatch/business authority. Nine new tests,77 combined pass in4.593s.833 not rerun or inherited; independent review PENDING.

原U1取消恢复已完成的239/85与旧固定833比较保留在原pin，不重复实现。本轮因新证据冲突优先消费并实现窗口合同，源对象身份/打开文件hash本轮未实现，继续下一离线项。祖先句柄不证明子文件内容/ACL/正式维护租约；真实Windows安装接线、publisher新文件/回滚合同、非交互出口及生产backend仍缺。回滚仅离线代码可git revert本轮源码提交；无生产备份/发布/安装动作。发布清单为两个源码文件加本目录证据/报告、canonical投影和checkpoint，不含原他人未跟踪目录。

Prior cancellation239/85 and833 comparison remain scoped to original pins. New evidence conflicts justified this cycle's consumption/window-contract work; source-object identity/open-file hashing remains next and is not implemented here. Ancestor handles do not prove child contents/ACL/formal lease. Real installer wiring, publisher new-file/rollback contract, egress and backend remain missing. Offline rollback is git revert of source commit; no production backup/release/install performed. Manifest: two source files, this evidence/report directory, queue projection and checkpoint; excludes others' untracked artifacts.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. allow_dispatch=false; allow_cancel_dispatch=false. 消费完成状态以随后独立回读CONSUMPTION_RECEIPT.json为准；本报告发布前验证记录false是该时点真实状态。Consumption completion depends on subsequent independently read-back receipt; prepublication verification false preserves that event's actual state.


封存 / Seal: Issue2消费回执6546897497已发布并逐字独立回读；CODEX_HANDOFF_CONSUMED=true，消费并非生产或无人登录验收。Issue2 receipt6546897497 published and independently read back verbatim; consumption true, production/unattended acceptance remains false. Receipt record: CONSUMPTION_RECEIPT.json.
