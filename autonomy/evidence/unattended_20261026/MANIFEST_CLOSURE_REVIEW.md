# 清单导入闭包独立审核 / Independent manifest import closure review

结论 / Verdict: PASS_FOR_PINNED_SOURCE_IMPORT_SMOKE_TEST

审查对象 / Reviewed test: `test_u1_manifest_closure.py`。
测试执行时 HEAD / HEAD at test execution: `9aa2f0fe9e8ce19af572d66080731bf7ef84b8f9`。测试代码随后固定于 / Test code subsequently pinned at: `621d3e4`（文件哈希复核一致 / unchanged file hash verified）。
实际 Windows 文件 SHA256 / Actual Windows file SHA256: `0d09c9938e9ffeb89c1f5eeb98ed44fa19e8562c71eddf7e3b2e3258f920af5f`。
清单源码提交 / Manifest source commit: `dbdc424ca9e83ccc8b7ff7d598f4a0f3b577f0b4`。

## 实际执行 / Execution

`python -B -m unittest test_u1_manifest_closure -v`: 2 tests passed, 0.933 seconds.

正例将清单指定 Git blob 字节逐项核对 SHA256 后写入临时目录；子进程使用当前解释器的 -I -B，并验证每个模块及已加载 autonomy 子模块均来自该临时目录。负例故意省略 unattended_policy，确实返回 ModuleNotFoundError，未从工作树补齐。 / The positive case verifies every manifest Git blob SHA256 before staging in a temporary directory. The child process uses the current interpreter with -I -B and verifies module origins inside that directory. Omitting unattended_policy in the negative case produces ModuleNotFoundError without checkout fallback.

实际执行了 Shanghai business-day conversion，且检查当前 sqlite3.Connection 暴露 deserialize。 / The probe executes Shanghai business-day conversion and checks that the current sqlite3.Connection exposes deserialize.

## 审核结论与界限 / Findings and limits

本次测试范围未发现阻断缺陷。测试不执行采集、任务安装或生产数据库操作，不改变 RELEASE_READY=false。 / No blocking defect was found in this test scope. It performs no collection, task installation or production database operation and keeps RELEASE_READY=false.

这只证明当前开发解释器上、固定清单的导入冒烟闭包。-I 不隔离系统安装包或替代生产运行时；时区数据版本、SQLite 原生库版本及其他部署依赖未固定。deserialize 属性存在不等于实际反序列化语义验收。XML 仅核对字节，未执行或验收。 / This establishes an import smoke closure for the pinned manifest on the current development interpreter only. -I does not isolate installed system packages or reproduce production. Timezone data, native SQLite versions and deployment dependencies are not pinned. deserialize attribute presence is not an actual deserialization acceptance test. XML bytes are verified but not executed or accepted.

不证明生产 runtime 依赖闭包、迁移兼容、生产部署、无人登录执行或业务增长。 / It does not establish production runtime dependency closure, migration compatibility, deployment, unattended execution without login or business growth.

