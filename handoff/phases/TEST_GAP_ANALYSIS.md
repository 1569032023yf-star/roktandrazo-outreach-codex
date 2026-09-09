# 测试缺口审计 / Test Gap Analysis

日期 / Date: 2026-09-08。方法 / Method: static inspection, no existing project tests executed.

中文：已有测试覆盖发送事务、门禁、模板、发现服务、时区、回流、人工审核等，不能说“没有测试”。缺口是最新补库链路、环境隔离和多入口并发缺乏对应的验证。下文“未发现”表示在副本测试源码中未找到直接覆盖，不代表数学上证明所有间接覆盖都不存在。

English: Existing tests cover send transactions, gates, templates, discovery, timezone, recovery and review. The gap is coverage of the latest replenishment wiring, environment isolation and multi-entry concurrency. “Not found” means no direct coverage located in the copied tests, not proof that all indirect coverage is absent.

## 已有覆盖 / Existing coverage

| 测试 / Tests | 已见内容 / Observed coverage | 限制 / Limitation |
|---|---|---|
| test_discovery_service.py | mock provider、游标、历史去重、staging/官网、缺官网转人工 / Mock provider, cursors, history and staging | 把 website_lookup_required 当终点，未证明自动找回官网。 / Does not complete automatic website recovery. |
| test_browser_maps_integration.py | 抓取结果、证据处理、集成 fixture / Browser results and evidence fixtures | 未见 env direct 经 load_provider 到真实模式的契约测试。 / No direct-mode env-to-factory contract test found. |
| test_manual_email_workflow.py, test_review_workflow.py | 人工提交、审核、历史 / Submission and review history | 未见真实 scanner 返回值直接接入 verifier 的测试。 / Scanner-to-verifier contract not found. |
| test_sender_transaction.py | 内存库与 mock SMTP、失败注入 / In-memory DB and mocked SMTP failures | 单线程事务测试不能证明 SMTP 与 DB 原子性或跨进程幂等。 / Single-process transaction tests do not prove distributed atomicity. |
| test_preflight_gate.py, test_p1_canonical_send_chain.py | 预检、授权、冻结计划 / Gates, authorization, frozen plans | tests 中未搜到 campaign_eligible_v2 直接引用，最新 V2 接线覆盖不足。 / No direct V2 reference found in tests. |
| test_single_smtp_authority.py | 静态 SMTP 引用与禁用标记 / Static markers | marker 检查不能证明 test_mode 无真实 SMTP。 / Marker presence does not prove runtime isolation. |
| timezone/recipient/business_rules/city_outreach_40 suites | 时区、城市队列、规则/40 日配额 / Timezone, city queue, rules/quota | 需加 SQLite UTC 与本地 stale cleanup 跨界及多执行器案例。 / Missing cross-clock stale cleanup and multiple-executor scenarios. |
| bounce/result_sync/reconciliation/email_tracking suites | 退信、回流、对账、tracking / Recovery and tracking | 需验证“局部成功不能刷绿旧 heartbeat”、外部副作用全拦截。 / Need freshness semantics and complete external-write isolation. |

## 建议补充的关键测试 / Required additional tests

| 优先级 / Priority | 案例 / Scenario | 通过标准 / Acceptance |
|---|---|---|
| P0 | 开发路径与网络边界 / Development path and network isolation | 继承生产环境、绝对路径、不同 cwd、子进程仍不能写生产/发 SMTP/改服务；所有 DB 路径拒绝越界。 / Inherited env, absolute paths, cwd changes and subprocesses cannot mutate production or contact SMTP. |
| P0 | 两个进程同时启动同阶段 / Concurrent same-stage launch | 只有一个持有者；被拒作业不得执行；锁释放验证 holder，过期时钟一致。 / One owner, rejected run never executes, owner-checked release and consistent expiry clock. |
| P0 | SMTP accepted 后 quit/commit 崩溃 / Failure after SMTP acceptance | 记录为 delivery-unknown 等待对账，禁止盲目重发；不把 DB rollback 当作 SMTP rollback。 / Reconcile unknown delivery before retry; DB rollback is not SMTP rollback. |
| P0 | test_mode=true 且 test_email 为空 / Empty test recipient | 在任何连接前拒绝；测试模式不得解锁 legacy SMTP。 / Reject before connecting; no legacy SMTP unlock. |
| P0 | 两轮 pre-send 与 outreach 同时运行 / Plan creation overlapping execution | 活跃授权计划不会被另一预发送取消/替换；同一 FSP 不发生二次发送。 / Active authorized plan is not replaced; each entry sent at most once. |
| P1 | env direct -> load_provider / Factory configuration | 没有缓存也选 direct；显式 file 模式优先级清楚。 / Direct mode works without cache; explicit override precedence tested. |
| P1 | 缺官网商户 -> 官网匹配 / Merchant-to-website resolver | 名称/电话/地址冲突拒绝；目录只作线索；匹配成功后可继续提取。 / Conflicts rejected; directories are hints; verified match advances. |
| P1 | scanner -> submit_manual_email | HTML 可见文本原片段满足校验；合成说明句失败且可以修复重试。 / Literal visible evidence passes; synthetic prose fails with retryability. |
| P1 | NY 官方邮箱 -> 上游候选 -> V2 / NY candidate pipeline | 上游不因旧 A0 地域门槛永久丢弃；是否可发仍由冻结 V2 决定。 / No premature discard by old A0 scope; frozen V2 remains final authority. |
| P1 | BroadReady=33, V2=0 | 库存不得宣称 SAFE 达标；继续补库或给出明确耗尽原因。 / Inventory cannot report SAFE completion; continue or explain exhaustion. |
| P1 | 浏览器多页/缓存回放 / Browser pages and cache replay | cursor 与页身份一致、重复页不算新增、TTL 不把旧结果当新发现。 / Page/cursor identity, deduplication and freshness validated. |
| P1 | 暂时失败再试 / Transient recovery | 失败提交可重试；已发送/退订永不因重试回新池。 / Failed submissions can retry; sent/suppressed never return to new pool. |
| P1 | 官方可见性/重定向/TLS / Visible first-party evidence | 忽略 script/隐藏/第三方邮箱；跨域需身份复核；TLS/HTTP 失败不产生合格证据。 / Reject hidden/third-party content; verify redirects; fail closed on TLS/HTTP errors. |
| P2 | 冻结 V2/MX 回归矩阵 / Frozen V2/MX matrix | MX_OK、新鲜缓存、NXDOMAIN/null/no-route/DNS unavailable、89/90/91 天、缺 timestamp、来源、组织去重、窗口与配额保持现有边界。 / Full MX/freshness/provenance/history/window/quota matrix. |
| P2 | 批次级预算/重试公平性 / Runtime budgets and retry fairness | 慢站/429/空结果不无限阻塞；待查队列不会被旧行占满。 / Bounded delays and fair retry progression. |
| P2 | 多副作用隔离 / Complete side-effect mocks | SMTP、IMAP APPEND、HTTP POST、Wrangler remote、subprocess、服务/调度全部拦截。 / Block every email, HTTP, cloud and OS mutation channel. |
| P2 | 端到端 fixtures / End-to-end fixtures | Mock discovery -> website -> visible evidence -> V2/MX -> development FSP，第二遍运行零重复入库；真实 SMTP 连接数=0。 / Complete fixture flow with idempotent rerun and zero real SMTP connections. |

## 本阶段验证结果 / Phase 1 verification

中文：实际运行的是 `audit_static.py` 标准库审计器，不是生产模块或旧测试。487 文件 AST 检查、两处历史语法错误、只读快照 integrity_check=ok；冻结文件 SHA-256 已记录并复核。没有依赖安装、SMTP/MX 网络测试或服务启动。现有测试是否全部通过未知，不沿用历史“269 passed”等结论。

English: Only the standard-library `audit_static.py` ran, not production modules or legacy tests. It inspected 487 Python files, found two historical syntax errors and confirmed snapshot integrity. Frozen hashes were recorded and rechecked. No dependencies, SMTP/MX network tests or services were run. Current test-suite pass status is unknown; historical pass counts are not reused.

中文：测试环境准备属于下一阶段：先在开发根创建全新 fixture DB 或从只读快照派生测试库，强制网络/路径隔离，再逐项运行。当前 `.env` 和启动拦截不应被当作完整测试沙箱；不要为了运行 tests 全局设置 BD_TEST_MODE=true。

English: Next-phase testing requires a fresh fixture database or a derived test database inside development, enforced network/path isolation, then targeted execution. Current startup/environment guards are not a complete test sandbox. Do not globally set BD_TEST_MODE=true merely to run tests.
