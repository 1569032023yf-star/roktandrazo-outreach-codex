# 本轮命令 / Cycle commands

- 定向 / Targeted: `python -X utf8 -B -m unittest test_provider_worker test_process_backend test_provider_adapter_binding -v` — 24 PASS.
- 全量 / Full: isolated detached6de5cf3 worktree, `python -X utf8 -B tools/run_comparable_suite.py <evidence>/clean-candidate-suite` —848 tests,37 FAIL/17 ERROR; no new failure/error IDs versus measured9d5ecb6.
- 构建 / Build: `python -X utf8 -B -m autonomy.build_u1_delivery --output <u1-delivery-operation-6de5cf3> --source-commit 6de5cf3d421e0073be905a57e0dd3cd2cc1024a6 --python-runtime <u1-runtime-32f0246> --runtime-manifest-sha256 5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e` — timeout1200seconds.
- 包验证 / Archive verification: `python -X utf8 -B autonomy/evidence/u1_worker_operation_20261105/verify_driver.py` — timeout min840seconds or cycle remaining minus180seconds.
- 实际包内探针 / Actual packaged probe: `python -X utf8 -B autonomy/evidence/u1_worker_operation_20261105/packaged_worker_probe.py` — isolated temporary backend/configuration, no external requests.
- 结果与恢复 / Results and recovery: `python -X utf8 -B autonomy/evidence/u1_worker_operation_20261105/finalize_checkpoint.py`.

所有命令禁止安装/派发/发信及生产账本写入。 All commands exclude installation, dispatch, email and production-ledger writes.
