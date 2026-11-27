# ROKT&RAZO 搜索看板：下一步迭代计划 / Dashboard next-iteration plan

日期 / Date: 2026-11-27（Asia/Taipei）

## 中文

### 1. 本版基线与边界

本目录是 8793 本机预览候选，正式桥接为 8791、原有看板为 8792；候选未安装或部署。启动预览命令：`python -B -m local_dashboard_v3_candidate.server --port 8793`。本次提交不代表生产发布，也不代表搜索已启动。

目前可以查看按州排列的城市目录、历史完成标记、已有城市的商家数据、查询明细和运行记录；可以准备本地草稿。城市目录来自美国人口普查局 2025 National Places，包括建制地区与 CDP，不包含所有非建制社区或所有镇区。同名城市不能自动确定归属时显示待核对。已存搜索记录不等于可准确计算搜索次数。

当前没有可靠的执行器心跳和本轮完整计数，因此实时状态、本轮结果和下次实际触发不能推测。正式任务写入入口尚未接通：选择城市或保存草稿不会加入正式队列，也不会启动搜索。现有“保留线索”是对历史记录的只读筛选，不是已经落地的独立线索库或人工补充功能。已完成城市所显示的商家资料也限于现有可读字段，并非所有原始采集数据。

历史核查线索：Lake Placid 已存地图查询组 20/20，但城市未关闭；历史关联记录 `ldr:653` 的完成判断和实际关联处理需核实，Oneonta 曾是下一候选。此为历史证据，不代表当前状态；任何修复前必须重新只读核对时间与原始记录。

### 2. 目标与完成顺序

目标是让用户可以确认是否真的在执行、查看一轮的工作和卡点，并在正式入口可用且安全条件满足后选择下一座城市。只保留原有正式桥接、唯一正式 Inventory 和现有调度权；不新建调度器或自动化，不恢复旧目标，不绕过邮件门禁。以下均是未来工作，不是已经实现的功能。

#### P0：建立可信基线，先找准正式入口

1. 只读比对运行中的 8791、8792、候选源码、Inventory 架构、任务队列以及已有发布入口的版本与权限；核实其他人的未提交修改和依赖，不覆盖、不改写。
2. 分别核实数据库可读性、桥接可用性、执行器是否提供心跳、现有触发及执行权记录；不能读取时记为未知，保留读取时间和错误分类。
3. 重新核查 Lake Placid 的查询完成、关联重试选择、关联处理数量、城市结束条件及历史恢复记录，定位证据链。不能因普通资料待补就强制关城，也不能省略执行权和在途请求检查。

交付和验收：一份带时间、来源和未知项的现状表；正式计划写入、发布和回滚通道是否存在均有依据。离线测试不调用真实搜索、邮件或生产写入。

#### P1：让执行过程有可靠回执

1. 为正式任务建立或复用稳定的任务 ID、城市 ID、搜索类型和范围版本；把每次执行、查询组、请求、保存结果与对应任务关联。没有可证实关系的旧记录保持历史或未知。
2. 在现有执行器内记录步骤、心跳、执行权持有人及有效期、请求是否在途、最近有效进展、错误及实际触发回执；计划时间和实际触发分开。
3. 给各数字定义口径：计划及完成查询组、发出请求、原始结果、去重后新商家、重复结果、官网、公开邮箱、已处理、失败和未知；单次与历史累计分开。查询组进度不叫全城覆盖率。
4. 提供最小只读状态接口，返回来源、采集时间、状态及缺失原因。看板区分新鲜、过期、不可用；心跳缺失只能显示无法确认，不能用最近作业代替在线状态。

验收：用模拟运行验证每个数能追溯到指定任务；断桥、数据库失败、心跳过期、请求结果未知时无虚假成功或虚假零值；展示当前、历史、未知互不混淆。

#### P2：修正城市结束与保留线索的关系

1. 对照 Lake Placid 的真实记录分析为什么 `ldr:653` 被视为可重试、为何实际处理为 0，以及结束条件和选择条件是否冲突；检查是否有已经结束的任务被重复恢复。先形成复现测试和原因，再改原有执行逻辑。
2. 将“本次约定搜索范围结束”与“商家资料完善、资格审核”作为两个独立状态。缺邮箱、官网待确认等普通保留线索可留给以后处理；有效执行权、在途请求、结果落库和任务安全检查仍须满足。
3. 在现有 Inventory 内设计兼容的保留线索数据及迁移：城市稳定身份、商家身份、名称/地址/官网/联系方式、发现来源和时间、当前分类、待解决原因、证据来源及变更历史；兼容旧人工审核记录，不覆盖或删除。
4. 人工补充邮箱、官网、备注和核实状态需附来源与变更记录，可撤销或更正；不得自动重新搜索、自动转为可发信或绕过原有资格与发送门禁。实际迁移和上线须通过正式渠道和门禁。

验收：用虚构数据重现“范围已完成但有 20 条缺邮箱”，安全检查满足后可结束搜索并保留全部线索；在途请求或执行权冲突时不切换；重复执行不丢数据、不重复关城；旧审核记录和审计历史可追溯。

#### P3：接通用户选城与原有队列

1. 检查现有正式计划入口与写入权限，以州、稳定城市标识、商家类型、已确认的范围形成请求；无唯一匹配时要求人工核对，不按名称猜测。计划名称、编号和记录由系统管理。
2. 在原有正式队列的受控入口内完成校验、原子写入与回执：验证城市状态、权限、队列版本和重复请求；用请求 ID 防重复，并向页面返回真实成功、冲突或失败。连接不可用时保留草稿并明确未提交。
3. 清楚区分“已准备”“已正式入队”“等待执行”“实际开始”“已完成”。入队本身不承诺立刻搜索；已经完成或已有待执行任务的城市需显示真实状态，重复、取消和排序按照正式规则处理。
4. 防止并发操作造成重复领取或跳城；仅由现有执行器取得执行权并执行，未建立安全约束前禁止绕过门禁手写数据库或增加第二套调度器。写接口需具备本机身份、来源/CSRF 防护、审计和幂等性。

验收：在隔离数据库和模拟桥接中验证正常提交及回读、同城重复点击、断网重试、两人同时提交、队列已变化、同名城市、服务重启；未获得正式回执时页面绝不显示成功。

#### P4：完善用户体验与发布准备

1. 州城市列表显示可解释的完成/排队/未知状态、可搜索筛选；完成城市可查看能追溯的全部已接通字段、来源和分页，缺失原始数据明确提示。展示“已搜过 X 次”前先定义并验证可追溯的一次搜索，缺证据显示次数未知。
2. 首页按当前状态、实际进度、卡点、下一步展示；每个问题包括影响对象、起始及最近进展、处理状态、建议和是否需用户决定，历史问题与当前问题分开。
3. 打包、独立审查、版本与迁移核验、回滚演练及正式入口的逐项门禁。只有验证后的指定版本才能进入受控发布；发布不等于真实搜索成功或允许发信。

验收：完成界面、接口、数据迁移和安全检查矩阵；真实环境只做授权范围内的核对。后续若要实际启动搜索，须有用户授权并通过正式入口及执行安全检查；商业邮件仍遵循单独授权和现有门禁。

### 3. 推荐依赖和验收场景

顺序：P0 → P1 → P2 → P3 → P4。P2 的线索数据结构可与 P1 的接口设计并行评审，但不可先改生产库；用户界面样式可并行，正式写入需等待 P0–P2 的安全依据。以上是优先级而非承诺工期。

必测场景：Lake Placid 查询结束与关联记录冲突；执行权失效但请求仍在途；来源超时后结果未知；重复请求与进程恢复；桥接或数据库不可用；城市同名；已有城市再次排队；人工修改留痕；搜索结果和历史库存隔离；未授权发送永远不可触发。

交接时分别报告：开发完成、测试通过、审查通过、可发布、已部署、真实搜索验收；任何未得到证据的阶段保持未完成或未知。本计划本身不会执行搜索、部署或发送。

## English

### 1. Baseline and boundaries

This directory is the local 8793 preview candidate; the existing bridge is 8791 and the existing dashboard is 8792. It has not been installed or deployed. Start a preview with `python -B -m local_dashboard_v3_candidate.server --port 8793`. This commit does not establish a production release or an active search.

The candidate displays a state-based city catalog, historical completion markers, available merchant fields, query details and run records, and supports local drafts. The 2025 U.S. Census National Places catalog contains incorporated places and CDPs, not every unincorporated community or township. Ambiguous city matches require verification; recorded history does not establish an accurate search count.

There is no reliable executor heartbeat or complete per-run accounting. Live status, current-run results and actual next trigger remain unknown. The formal write endpoint is disconnected: selecting a city or saving a draft neither queues nor starts a search. Retained leads are currently a read-only filter over historical rows, not a dedicated lead store or an editing workflow. Completed-city details show available fields only, not necessarily all original collected material.

Historical evidence showed 20/20 stored map query groups for Lake Placid, an unclosed city and an apparent mismatch involving `ldr:653`; Oneonta was a next candidate. These are historical clues, not current status. Recheck source records and timestamps read-only before any repair.

### 2. Ordered delivery plan

Keep the official bridge, one formal Inventory and existing scheduling authority. Add no scheduler or automation, restore no old target, and bypass no email gates. Everything below is future work, not an implemented claim.

**P0 — Establish the baseline.** Read-only compare running versions, repository changes, Inventory schema, queue, supported release and rollback channels, without overwriting others' work. Verify bridge/database access, heartbeat availability, trigger and lease evidence. Re-investigate Lake Placid's retry selection, actual processing, completion and recovery records. Deliver a timestamped evidence and unknowns table; perform offline tests without production writes, real searches or email.

**P1 — Add trustworthy execution receipts.** Reuse or define stable task/city IDs and scope versions; associate runs, query groups, requests and results where evidence supports it. Record steps, heartbeat, lease holder/expiry, in-flight requests, meaningful progress, errors and actual triggers inside the existing executor. Define per-run versus historical counters, including requests, raw results, distinct new merchants, duplicates, websites, public emails, processed, failures and unknowns. Provide a minimal read-only status interface with source and observation time. Test stale heartbeat, bridge/database failures and unknown outcomes without invented zeros or success; query-group progress is not city coverage.

**P2 — Separate search completion from retained leads.** Reproduce the historical `ldr:653` mismatch and investigate repeated recovery before changing existing logic. Separate search-range completion from merchant enrichment and qualification, while preserving lease, in-flight request, persistence and execution safety checks. Design a backward-compatible Inventory migration for city and merchant identity, contact information, source, discovery time, classification, unresolved reasons, evidence and change history. Preserve old reviews. Future human edits require source and audit history and must not automatically restart searches or authorize sending. In isolated tests, a completed search with 20 missing-email leads can close when safety checks pass, retain all leads, and must not switch while requests or execution rights conflict.

**P3 — Connect city selection to the existing queue.** Identify the supported write endpoint and permissions; submit stable city identity, merchant type and confirmed scope. Ambiguous identities require verification. Validate authorization and queue version, use atomic writes and idempotent request IDs, and return a real receipt; keep a draft and show failure when disconnected. Distinguish prepared, formally queued, waiting, actually started and completed. Prevent concurrent claims or duplicate submissions through the existing authority, with local authentication, origin/CSRF protection and audit records. Test retries, simultaneous users, restarts, duplicate cities and changed queue state using isolated fixtures; never show success without a receipt.

**P4 — Finish user experience and release preparation.** Explain city completion/queue/unknown states, provide searchable lists and paginated traceable available fields, and label unavailable original data. Show a search count only when its definition and evidence are validated. Present current status, actual progress, blockers and next action with timestamps, affected items, handling and decision needs, separating history from active issues. Require packaging, independent review, migration checks, rollback rehearsal and supported release gates. Production release, actual search acceptance and permission to send email are separate outcomes; any future real search requires user authorization and execution safeguards.

### 3. Dependencies and verification

Order: P0 → P1 → P2 → P3 → P4. Retained-lead schema design may be reviewed alongside P1, but do not change the production database early. Interface styling may run in parallel; formal writes depend on the P0–P2 safety evidence. This order is a priority, not a delivery-date promise.

Required scenarios include the Lake Placid completion/retry mismatch, expired lease with a request still in flight, unknown provider outcomes, duplicate requests and recovery, bridge/database failures, same-name cities, re-queuing, audited manual edits, isolation of per-run results from historical inventory, and prevention of unauthorized sending. Handoffs must distinguish development complete, tests passed, review passed, release ready, deployed and real-search accepted; unsupported claims remain incomplete or unknown. This plan itself runs no search, deployment or email.
