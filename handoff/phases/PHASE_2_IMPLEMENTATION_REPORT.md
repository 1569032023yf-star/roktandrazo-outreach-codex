# Phase 2A / 2B Implementation Report | Phase 2A / 2B 实施报告

## 1. Outcome | 结果

Phase 2A and the development-only Phase 2B replenishment loop are implemented in the development copy. The production source, live database, production services, WorkBuddy automations, and real SMTP were not touched or invoked.

Phase 2A 与仅限开发环境的 Phase 2B 补库闭环已在开发副本中实现。生产源目录、生产数据库、生产服务、WorkBuddy 自动化和真实 SMTP 均未被修改或调用。

```text
PRODUCTION_ROOT = C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach
DEVELOPMENT_ROOT = C:\Users\15690\Documents\ChatGPT\线下\roktandrazo-outreach-dev

PRODUCTION_MODIFIED = false
LIVE_DB_WRITE_ENABLED = false
REAL_SMTP_ENABLED = false
FROZEN_SEND_CHAIN_MODIFIED = false
```

## 2. Phase 2A — Development Safety | Phase 2A — 开发安全

- A `.development-copy` marker and `development_safety.py` provide fail-closed development guards. The installer is idempotent so repeated imports do not recursively wrap runtime APIs.
- `.development-copy` 标记与 `development_safety.py` 提供故障关闭式开发防护；安装过程具备幂等性，多次导入不会重复递归包裹运行时 API。
- Database paths are limited to in-memory databases, this development root, or the operating-system temporary directory. The production root is explicitly rejected.
- 数据库路径仅允许内存数据库、本开发根目录或操作系统临时目录；生产根目录被明确拒绝。
- `.env` contains only development placeholders and points to `data/bd_leads_dev_runtime.db`. The production snapshot remains read-only as `data/bd_leads_dev_snapshot.db` and the runtime database has not been created by the tests.
- `.env` 仅包含开发占位配置，并指向 `data/bd_leads_dev_runtime.db`。生产快照以只读形式保留为 `data/bd_leads_dev_snapshot.db`，测试未创建运行时数据库。
- External socket, SMTP, IMAP, shell, and unsafe subprocess paths are blocked when the development marker is active. Core loaders explicitly install the guard instead of relying only on automatic `sitecustomize` loading.
- 开发标记生效时，外部 socket、SMTP、IMAP、shell 和不安全子进程路径均被阻断；核心加载器会显式安装防护，而不是只依赖 `sitecustomize` 自动加载。

## 3. Phase 2A — Job Mutual Exclusion | Phase 2A — 作业互斥

- `acquire_run_lock` now uses `BEGIN IMMEDIATE` and atomic upserts, preventing two independent SQLite connections from both winning the same lock.
- `acquire_run_lock` 现在使用 `BEGIN IMMEDIATE` 与原子 upsert，防止两个独立 SQLite 连接同时获得同一把锁。
- Lock release requires the matching holder ID; a non-owner cannot release another run's lock.
- 释放锁必须匹配持有者 ID，非持有者无法释放其他运行的锁。
- `start_job_run` is transactionally serialized. The orchestrator exits before executing a stage when duplicate job registration is rejected.
- `start_job_run` 采用事务串行化；重复作业注册被拒绝时，编排器会在执行任何阶段前退出。

## 4. Phase 2B — Safe Replenishment Loop | Phase 2B — 安全补库闭环

Implemented flow / 已实现流程：

```text
Discovery
  -> Website resolution with identity scoring
  -> Official-page email extraction
  -> First-party evidence validation
  -> Frozen V2 and MX decision
  -> development-only Dev FSP materialization
```

- Website resolution scores business name, phone, and location evidence; social-media and directory URLs are rejected as official sites.
- 官网解析按商户名称、电话和地点证据评分；社交媒体与目录站点不会被提升为官方网站。
- Missing websites stay in `website_lookup_pending` instead of being prematurely converted into manual-review leads.
- 缺少官网的对象会保留在 `website_lookup_pending`，不会过早转成需要人工审查的 lead。
- Official-page extraction rejects failed HTTP status, failed TLS evidence, identity mismatch, and cross-domain redirects.
- 官方页面抽取对失败 HTTP 状态、TLS 证据失败、身份不匹配和跨域重定向采取故障关闭策略。
- New leads now carry `organization_key`, recipient timezone, and timezone status when inserted.
- 新 lead 写入时会携带 `organization_key`、收件人时区和时区状态。
- `dev_safe_fsp` is a separate development-only table. It calls the unchanged frozen V2/MX review path and is not consumed by any sender.
- `dev_safe_fsp` 是独立的开发专用表；它调用未修改的冻结 V2/MX 审核路径，并且不会被任何发送器消费。
- `safe_replenishment.run_development_funnel` provides one callable, testable loop and reports funnel counts and `smtp_calls = 0`.
- `safe_replenishment.run_development_funnel` 提供一个可调用、可测试的完整闭环，并报告漏斗计数及 `smtp_calls = 0`。

## 5. Frozen Chain Verification | 冻结链验证

The SHA-256 values in `audit_evidence/frozen_sha256.json` still match all five frozen files:

`audit_evidence/frozen_sha256.json` 中的 SHA-256 仍与以下五个冻结文件完全一致：

- `bd_sender.py`
- `daily_session.py`
- `preflight_gate.py`
- `campaign_eligible_v2.py`
- `final_send_plan.py`

All five checks returned `Match = True` on 2026-09-08.

五项校验在 2026-09-08 均返回 `Match = True`。

## 6. Verification | 验证

Targeted offline tests / 定向离线测试：

```text
tests.test_phase2a_safety_mutex
tests.test_phase2b_safe_replenishment
tests.test_discovery_service

Ran 28 tests
Result: PASS (28/28)
```

The tests cover production-path rejection, SMTP fail-closed behavior, lock contention, lock ownership, duplicate orchestrator suppression, end-to-end fixture replenishment, identity rejection, redirect rejection, idempotent lead creation, and zero SMTP calls.

测试覆盖生产路径拒绝、SMTP 故障关闭、锁竞争、锁所有权、重复编排抑制、端到端 fixture 补库、身份拒绝、重定向拒绝、lead 幂等创建及零 SMTP 调用。

Full legacy suite snapshot / 完整旧测试集快照：

```text
Ran 233 tests in 31.195s
FAILED (failures=8, errors=18)
```

This full-suite result is not declared green. Observed baseline/environment gaps include missing `pytest`, missing Windows timezone data (`tzdata`), stale tests that import absent legacy inventory modules, hand-built test databases missing newer tables, and a frozen preflight test/implementation mismatch. These are recorded as follow-up work and were not bypassed by changing frozen send logic.

完整测试集未被宣称为通过。已观察到的基线/环境缺口包括：缺少 `pytest`、Windows 时区数据包 `tzdata` 缺失、陈旧测试仍导入已不存在的旧库存模块、手工测试数据库缺少较新表，以及冻结 preflight 测试与实现不一致。本阶段没有通过修改冻结发送逻辑来绕过这些问题，后续应单独处理。

## 7. Scope Boundary and Next Gate | 范围边界与下一道门

This implementation proves a development-only replenishment path through Dev FSP. It does **not** authorize production deployment, scheduler activation, real provider traffic, live MX traffic, live database writes, or real outreach. Promotion requires a separate review of the failing legacy suite, dependency pinning, controlled provider integration tests, and an explicit production change approval.

本次实现证明了仅限开发环境、最终落到 Dev FSP 的补库路径。它**不代表**已授权生产部署、调度器启用、真实 provider 流量、真实 MX 流量、生产数据库写入或真实外联。进入生产前，必须另行审查旧测试集失败项、锁定依赖、执行受控 provider 集成测试，并取得明确的生产变更授权。
