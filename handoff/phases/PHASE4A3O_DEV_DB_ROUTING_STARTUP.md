# Phase 4A.3O — Verify Dev DB Routing and Pre-Stage Startup / 开发 DB 路由与预阶段启动验证

## Decision / 决定

`ROOT_CAUSE = DEV_DB_PATH_OVERRIDE`.

The development safety guard previously replaced a caller-supplied safe database-copy path with the default development runtime path. The narrow development-only repair preserves the first explicitly supplied, validated file-backed path and restores it at later `install()` calls, including after `env_loader` imports.

开发安全护栏此前会用默认开发运行库路径替换调用方提供的安全数据库副本路径。此次狭窄的开发专用修复会保留首次显式提供且经验证的文件型路径，并在后续 `install()` 调用（包括 `env_loader` 导入后）恢复它。

## A. Effective DB routing / 实际 DB 路由

### Before repair / 修复前

| Field / 字段 | Observed value / 观测值 |
|---|---|
| `INTENDED_COPY_PATH` | `.../_audit_quarantine/phase4a3o/routing_probe_copy.db` |
| `ENV_DB_PATH_BEFORE_PYTHON` | Intended copy path / 目标副本路径 |
| `ENV_DB_PATH_AFTER_SITECUSTOMIZE` | `.../data/bd_leads_dev_runtime.db` |
| `ENV_DB_PATH_AFTER_ENV_LOADER` | `data/bd_leads_dev_runtime.db` |
| `BD_DB_DB_PATH_AFTER_IMPORT` | `.../data/bd_leads_dev_runtime.db` |
| `INTENDED_COPY_PATH_USED_BY_BD_DB` | `false` |

### After repair / 修复后

| Field / 字段 | Observed value / 观测值 |
|---|---|
| `INTENDED_COPY_PATH` | `.../_audit_quarantine/phase4a3o/startup_probe_copy.db` |
| `ENV_DB_PATH_AFTER_SITECUSTOMIZE` | Intended copy path / 目标副本路径 |
| `ENV_DB_PATH_AFTER_ENV_LOADER` | `data/bd_leads_dev_runtime.db` (development `.env` value / 开发 `.env` 值) |
| `BD_DB_DB_PATH_AFTER_IMPORT` | Intended copy path / 目标副本路径 |
| `EFFECTIVE_DB_IS_INTENDED_COPY` | `true` |
| `STARTUP_IMPORT_COMPLETED` | `true` |
| `START_JOB_RUN_CAN_WRITE_TO_COPY` | `true` |
| `DIAGNOSTIC_JOB_RUN_CLEANED_UP` | `true` |

`data/bd_leads_dev_runtime.db` did not exist at inspection time; therefore it contains no matching Phase 4A.3N `job_run` or current execution state. This establishes `PHASE4A3N_JOB_FOUND_IN_DEFAULT_DEV_DB = false`. It does not invent a claim that the stopped Phase 4A.3N harness reached a production pipeline stage.

检查时 `data/bd_leads_dev_runtime.db` 不存在；因此其中没有匹配的 Phase 4A.3N `job_run` 或当前执行状态。故 `PHASE4A3N_JOB_FOUND_IN_DEFAULT_DEV_DB = false`。这并不虚构“已停止的 Phase 4A.3N 演练曾进入生产管道阶段”的结论。

## B. Bounded pre-stage import trace / 有界预阶段导入追踪

No external BrowserMaps, SMTP, or IMAP calls were made. Each independent import completed within the 15-second bound.

未调用外部 BrowserMaps、SMTP 或 IMAP。每个独立导入均在 15 秒上限内完成。

| Module / 模块 | Completed / 完成 | Elapsed ms / 耗时毫秒 | Last import if timeout / 超时最后导入 |
|---|---:|---:|---|
| `sitecustomize` | true | 0.01 | none / 无 |
| `env_loader` | true | 2.95 | none / 无 |
| `history_crosscheck` | true | 5.62 | none / 无 |
| `bd_db` | true | 6.17 | none / 无 |
| `outreach_control` | true | 35.34 | none / 无 |
| `bd_orchestrator` | true | 38.30 | none / 无 |

## C. Narrow change / 狭窄变更

Only these development artifacts changed:

- `development_safety.py`: adds `_select_safe_database_path()`; validates explicit development/temporary database paths; rejects production and other external paths; preserves the validated explicit path across subsequent guard installation.
- `tests/test_phase4a3o_dev_db_routing.py`: regression coverage for explicit development and temporary paths, production/external rejection, and default fallback.

仅变更以下开发制品：

- `development_safety.py`：新增 `_select_safe_database_path()`；验证显式开发/临时数据库路径；拒绝生产及其他外部路径；在后续护栏安装中保留经验证的显式路径。
- `tests/test_phase4a3o_dev_db_routing.py`：覆盖显式开发与临时路径、生产/外部路径拒绝、默认回退的回归测试。

No production source, discovery provider, sender, V2, MX, template, or frozen file changed.

未变更任何生产源码、发现提供者、发送器、V2、MX、模板或冻结文件。

## D. Validation / 验证

- Targeted tests: `13 passed`.
- Full suite: `354 passed, 76 subtests passed in 75.87s`; `FAILED = 0`; `ERRORS = 0`.
- Startup probe: the diagnostic `job_run` was created and removed on the fresh copy only. `stage_inventory()` was not invoked.

- 定向测试：`13 passed`。
- 全套测试：`354 passed, 76 subtests passed in 75.87s`；`FAILED = 0`；`ERRORS = 0`。
- 启动探针：诊断 `job_run` 仅在新鲜副本中创建并删除。未调用 `stage_inventory()`。

## Safety / 安全

`PRODUCTION_FILES_CHANGED = 0`; `PRODUCTION_DB_WRITES = 0`; `SMTP_CONNECTIONS = 0`; `IMAP_CONNECTIONS = 0`; `BROWSERMAPS_CALLS = 0`; `SCHEDULER_CHANGES = 0`; `FROZEN_FILES_CHANGED = 0`.

`生产文件变更 = 0`；`生产数据库写入 = 0`；`SMTP 连接 = 0`；`IMAP 连接 = 0`；`BrowserMaps 调用 = 0`；`调度变更 = 0`；`冻结文件变更 = 0`。

## Final state / 最终状态

`READY_TO_RERUN_FINAL_INVENTORY = true` because the effective DB target is proven, startup imports complete, the intended copy receives the diagnostic job run, and production remains untouched.

`READY_TO_RERUN_FINAL_INVENTORY = true`，因为已证明实际 DB 目标正确、启动导入完成、目标副本可接收诊断 job run，且生产未被触碰。

Stop. The final Inventory rerun requires the next explicit authorization. Do not deploy or resume scheduling.

停止。最终 Inventory 重跑需要下一次明确授权。不得部署或恢复调度。
