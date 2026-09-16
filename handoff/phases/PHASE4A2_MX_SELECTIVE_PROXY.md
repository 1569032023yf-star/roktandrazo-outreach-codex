# PHASE 4A.2 — MX-only selective proxy narrow fix / 仅 MX 选择性代理窄修复

## Decision / 决策

`READY_FOR_CONTROLLED_PRODUCTION_PATCH = true`。开发验证、定向网络演练和全套回归均通过；仍需要明确的生产补丁批准以及部署时对实际生产基线哈希的验证。未部署，未恢复调度。

`READY_FOR_CONTROLLED_PRODUCTION_PATCH = true`. Development validation, the targeted network rehearsal, and the full regression suite passed; explicit production-patch approval and deployment-time validation of the actual production baseline hash are still required. Nothing was deployed and scheduling was not resumed.

## Root cause and scope / 根因与范围

- `ROOT_CAUSE_CONFIRMED = true`：`preflight_gate.query_mx` 原来调用默认 `urllib.request.urlopen`。默认 opener 会读取进程级 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`，所以 MX 请求会继承通用代理状态。
- `ROOT_CAUSE_CONFIRMED = true`: `preflight_gate.query_mx` previously called default `urllib.request.urlopen`. The default opener reads process-wide `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY`; therefore MX requests inherited generic proxy state.
- `MX_PROXY_CONFIG_KEY = BD_MX_HTTPS_PROXY`。该键是可选配置，不包含代理地址、凭据或令牌。
- `MX_PROXY_CONFIG_KEY = BD_MX_HTTPS_PROXY`. This optional key contains no proxy address, credential, or token in this repository.
- `PRODUCTION_FILES_CHANGED_IN_PATCH = 1`：仅 `preflight_gate.py`。没有 schema、环境文件、调度、发送或 V2 业务策略改动。
- `PRODUCTION_FILES_CHANGED_IN_PATCH = 1`: only `preflight_gate.py`. There is no schema, environment-file, scheduler, sending, or V2 business-policy change.

## Call-path audit / 调用路径审计

`env_loader.py` 负责读取环境；Worker 鉴权仍按既有顺序使用 `TRACKING_DASHBOARD_API_KEY`，再兼容 `DASHBOARD_API_KEY`，最后是历史兼容回退。该回退值未在报告、测试输出或 Git 中披露，也未被修改。`campaign_eligible_v2.py` 的候选选择和库存扫描会通过既有 `query_mx` 路径获得 MX 状态；`preflight_gate.check_dns_freshness` 也可调用该路径。`campaign_eligible_v2._website_reachable` 仍是独立的普通网站探测，保持默认 HTTP 行为，未被此补丁改变。

`env_loader.py` loads the environment; Worker authentication retains its existing order: `TRACKING_DASHBOARD_API_KEY`, then compatible `DASHBOARD_API_KEY`, then a historical compatibility fallback. That fallback value was neither disclosed in reports/test output/Git nor changed. Candidate selection and inventory scans in `campaign_eligible_v2.py` obtain MX status through the existing `query_mx` path; `preflight_gate.check_dns_freshness` can also call it. `campaign_eligible_v2._website_reachable` remains a separate ordinary website probe with unchanged default HTTP behavior.

The historical embedded fallback is a pre-existing security debt. It is outside this narrow change and must be removed only through a separately approved credential-rotation work item.

历史内嵌回退是既有安全债务，不属于本次窄修复；仅可在单独批准的凭据轮换任务中移除。

## Implemented behavior / 已实现行为

| Check / 检查项 | Before / 修改前 | After / 修改后 |
| --- | --- | --- |
| MX request routing / MX请求路由 | Default opener inherited process globals / 默认opener继承进程全局代理 | Local MX-only opener / 本地仅MX opener |
| Configured proxy / 已配置代理 | No scoped config / 无作用域配置 | `ProxyHandler({"https": BD_MX_HTTPS_PROXY})` only for MX Worker HTTPS / 仅 MX Worker HTTPS |
| No configured proxy / 未配置代理 | Could inherit globals / 可能继承全局代理 | `ProxyHandler({})`, direct and global-proxy-free / 直连且不继承全局代理 |
| Other urllib traffic / 其他urllib流量 | Shared default behavior / 共享默认行为 | Unchanged; `BD_MX_HTTPS_PROXY` does not affect it / 不变；不受该键影响 |
| Failure handling / 失败处理 | Existing DNS fallback then fail-closed status / 既有DNS回退后fail-closed | Unchanged / 不变 |

`MX_REQUEST_INHERITS_GLOBAL_PROXY_BEFORE = true`。

`MX_REQUEST_INHERITS_GLOBAL_PROXY_AFTER = false`。

`NON_MX_TRAFFIC_AFFECTED_BY_BD_MX_PROXY = false`。

## Verification / 验证

### Targeted tests / 定向测试

Six routing assertions passed: configured proxy is scoped to HTTPS; an explicit MX proxy overrides a conflicting global proxy; global proxy alone is ignored; the new environment key does not alter default urllib proxy discovery; proxy failure preserves the existing DNS fallback/fail-closed result; and a valid Worker response remains `ok`.

六项路由断言全部通过：配置代理仅作用于 HTTPS；显式 MX 代理覆盖冲突的全局代理；仅有全局代理时被忽略；新环境键不改变默认 urllib 代理发现；代理失败仍保持既有 DNS 回退/fail-closed 结果；有效 Worker 响应仍为 `ok`。

`V2_ELIGIBILITY_DIFF_COUNT = 0`：使用当前真实漏斗的固定测试夹具，在相同 MX `ok` 输入下比较 `tier`、`eligible`、`pool`、`blockers` 和 `mx_status`，前后结果完全相同。

`V2_ELIGIBILITY_DIFF_COUNT = 0`: a fixture using the current real funnel compared `tier`, `eligible`, `pool`, `blockers`, and `mx_status` under the same MX `ok` input; results were identical.

`TARGETED_TESTS = 26 passed`。

`FULL_SUITE = 335 passed + 76 subtests; 0 failed, 0 errors`。

### One controlled network rehearsal / 一次受控网络演练

One process-only rehearsal set a deliberately conflicting generic HTTP(S) proxy and the optional MX-only configuration, then queried exactly three public domains: `yahoo.com`, `gmail.com`, and `robotcitygames.com`. All three Worker responses were `ok`; the local MX opener was invoked three times and was the only component using the MX-specific proxy.

一次仅进程内演练故意设置冲突的通用 HTTP(S) 代理以及可选的仅 MX 配置，然后仅查询三个公开域名：`yahoo.com`、`gmail.com` 与 `robotcitygames.com`。三个 Worker 响应均为 `ok`；本地 MX opener 被调用三次，且它是唯一使用 MX 专用代理的组件。

`REAL_NETWORK_REHEARSAL_RUN = true`。

`WORKER_REHEARSAL_PASS = true`。

`REAL_SMTP_CONNECTIONS = 0`; `REAL_IMAP_CONNECTIONS = 0`; `PRODUCTION_DB_WRITES = 0`; `PRODUCTION_FILES_CHANGED = 0`; `PRODUCTION_DEPLOYED = false`。

## Controlled production patch checklist / 受控生产补丁清单

1. Place the canonical scheduler authority under the separately approved maintenance hold; do not resume it. / 将规范调度权威置于单独批准的维护保持状态；不要恢复。
2. Back up the production database and the original `preflight_gate.py`; verify the SQLite backup. / 备份生产数据库和原始 `preflight_gate.py`；验证 SQLite 备份。
3. Verify the production baseline SHA-256 for `preflight_gate.py` before applying the artifact. The observed current production baseline is `b1f44038c346bbf022a9d40575e330a1a73471a6dafe0605d17eeacf3b8ef105`. / 应用制品前验证生产 `preflight_gate.py` 基线 SHA-256；已观测基线如前。
4. Apply only the approved local-opener change. Recompute and record the target hash from the exact production-host bytes. / 仅应用已批准的本地 opener 改动；从生产主机上的精确字节重新计算并记录目标哈希。
5. Add `BD_MX_HTTPS_PROXY` only if an MX-specific local proxy is operational; do not copy development `.env`, credentials, or generic global proxy variables. / 仅当仅MX本地代理可用时添加该键；不要复制开发 `.env`、凭据或通用全局代理变量。
6. Run no Inventory, PreSend, Outreach, SMTP, IMAP, authorization, or final-send-plan creation as part of this patch validation. / 补丁验证中不运行 Inventory、PreSend、Outreach、SMTP、IMAP、授权或最终发送计划创建。

## Final fields / 最终字段

```text
ROOT_CAUSE_CONFIRMED = true
MX_PROXY_CONFIG_KEY = BD_MX_HTTPS_PROXY
MX_REQUEST_INHERITS_GLOBAL_PROXY_BEFORE = true
MX_REQUEST_INHERITS_GLOBAL_PROXY_AFTER = false
NON_MX_TRAFFIC_AFFECTED_BY_BD_MX_PROXY = false
PRODUCTION_FILES_CHANGED_IN_PATCH = 1 (preflight_gate.py only)
FILES_CHANGED = preflight_gate.py; tests/test_preflight_gate.py; tests/test_phase4a2_v2_transport_regression.py; handoff artifacts
V2_POLICY_CHANGED = false
V2_ELIGIBILITY_DIFF_COUNT = 0
TARGETED_TESTS = 26 passed
FULL_SUITE = 335 passed + 76 subtests; 0 failed, 0 errors
REAL_NETWORK_REHEARSAL_RUN = true
WORKER_REHEARSAL_PASS = true
SECRET_COMMITTED = false
PRODUCTION_DEPLOYED = false
READY_FOR_CONTROLLED_PRODUCTION_PATCH = true
```
