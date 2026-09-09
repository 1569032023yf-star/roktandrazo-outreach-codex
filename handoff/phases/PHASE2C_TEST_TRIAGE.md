# Phase 2C Test Triage | Phase 2C 测试分诊

## Outcome | 结果

The development release-candidate suite is green after targeted environment, fixture-schema, and stale-test corrections. No frozen production logic was changed.

在仅修正开发环境、fixture schema 与陈旧测试后，开发发布候选完整测试集已全绿。未修改任何冻结生产逻辑。

```text
FULL_SUITE_TOTAL = 303
FULL_SUITE_PASS = 303
FULL_SUITE_FAIL = 0
FULL_SUITE_ERROR = 0
SUBTEST_PASS = 44
REAL_PHASE2_REGRESSIONS = 0
```

Command / 命令：`.venv\Scripts\python.exe -m pytest -q`

Result / 结果：`303 passed, 44 subtests passed in 55.36s`

## Development dependencies | 开发依赖

The development-only manifest is `requirements-dev.txt`; it must not be installed into production Python.

开发专用依赖清单为 `requirements-dev.txt`；禁止安装到生产 Python。

| Dependency / 依赖 | Pinned version / 锁定版本 | Verification / 验证 |
|---|---:|---|
| pytest | 9.1.1 | import + full suite / 导入及完整套件 |
| tzdata | 2026.3 | IANA/DST tests / IANA 与夏令时测试 |
| playwright | 1.62.0 | guarded import + controlled provider run / 安全层导入及受控 provider 运行 |
| httpx | 0.28.1 | import smoke test / 导入冒烟测试 |
| dnspython | 2.8.0 | import smoke test; controlled MX path available / 导入冒烟测试；受控 MX 路径可用 |

## Canonical test database contract | 规范测试数据库契约

`tests/schema_fixture.py` now builds one current development schema and asserts `TEST_SCHEMA_CONTRACT_VERSION = 1`. It covers Discovery, website resolution, email evidence, V2/FSP, job locks, reply/bounce/runtime support, and fails clearly on stale fixture versions. Tests never use the production snapshot.

`tests/schema_fixture.py` 现统一构建当前开发 schema，并断言 `TEST_SCHEMA_CONTRACT_VERSION = 1`。覆盖 Discovery、官网解析、邮箱证据、V2/FSP、作业锁、回复/退信/运行时支持；陈旧 fixture 版本会明确失败。测试从不使用生产快照。

## Frozen-chain verification | 冻结链验证

All five SHA-256 values exactly match `audit_evidence/frozen_sha256.json`.

五个 SHA-256 均与 `audit_evidence/frozen_sha256.json` 完全一致。

```text
FROZEN_FILES_CHANGED = 0
```

Detailed baseline classification is in `LEGACY_TEST_TRIAGE.md`. / 完整基线逐项分类见 `LEGACY_TEST_TRIAGE.md`。

