# 本轮命令 / Cycle commands

- 定向 / Targeted: `python -X utf8 -B -m unittest test_provider_worker test_single_slot_adapter test_provider_contracts -v` —46 PASS. Initial fixture exit error preserved in INITIAL_FAILURE.txt.
- 全量 / Full: isolated detached21568c8 worktree, `python -X utf8 -B tools/run_comparable_suite.py <evidence>/clean-candidate-suite` —848 tests,37 FAIL/17 ERROR; no added failure/error IDs versus measured6de5cf3.
- 构建 / Build: `python -X utf8 -B -m autonomy.build_u1_delivery --output <u1-delivery-search-21568c8> --source-commit 21568c8267d7d20b3127eab8d3f5c866202868fd --python-runtime <u1-runtime-32f0246> --runtime-manifest-sha256 5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e` —1200second timeout.
- 解压验证 / Extraction verification: `python -X utf8 -B autonomy/evidence/u1_search_binding_20261105/verify_driver.py` —min840seconds or cycle remaining minus180seconds.
- 包内探针 / Packaged probe: `python -X utf8 -B autonomy/evidence/u1_search_binding_20261105/packaged_worker_probe.py` —actual packaged CPython, isolated backend, bound browser_maps search request, zero external requests.
- 恢复同步 / Recovery synchronization: `python -X utf8 -B autonomy/evidence/u1_search_binding_20261105/finalize_checkpoint.py`.

未安装、未派发、未发信、未写生产账本。 No installation, dispatch, email or production-ledger writes.
