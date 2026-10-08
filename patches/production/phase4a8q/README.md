# Phase 4A.8Q production hotfix / 生产热修补丁

This directory contains the one-hunk production patch for `discovery/discovery_service.py`.
The source is pinned to commit `641b36b87af596a503cdcb8fb518eab66d5ffbb9`; see `BASELINE.txt` for the Git blob ID and full-file SHA-256 values.

本目录仅包含针对 `discovery/discovery_service.py` 的单处状态迁移生产补丁。源代码基线固定为提交 `641b36b87af596a503cdcb8fb518eab66d5ffbb9`；Git blob 与完整文件 SHA-256 见 `BASELINE.txt`。

## Apply and verify / 应用与验证

1. Obtain `discovery/discovery_service.py` from the pinned commit and verify its SHA-256 equals `PRODUCTION_BASELINE_SHA256`.
2. Stop immediately if the actual production file hash differs. Re-audit the production source before any deployment consideration.
3. From the repository root, run `git apply --check patches/production/phase4a8q/identity_review_terminal.patch`, then apply that patch.
4. Verify the patched file SHA-256 equals `PRODUCTION_PATCHED_SHA256`.
5. Run `python -m py_compile discovery/discovery_service.py` and `python patches/production/phase4a8q/verify_production_patch.py discovery/discovery_service.py`.

1. 从固定提交取得目标文件，并确认 SHA-256 等于 `PRODUCTION_BASELINE_SHA256`。
2. 若生产实际文件哈希不同，立即停止；先重新审计生产源码，再考虑部署。
3. 在仓库根目录运行 `git apply --check patches/production/phase4a8q/identity_review_terminal.patch`，再应用补丁。
4. 确认补丁后文件 SHA-256 等于 `PRODUCTION_PATCHED_SHA256`。
5. 执行 `python -m py_compile discovery/discovery_service.py` 和 `python patches/production/phase4a8q/verify_production_patch.py discovery/discovery_service.py`。

The patch does not create leads, emails, SAFE/send eligibility, review-desk items, or send plans. `identity_review` remains queryable from `lead_discovery_results` audit fields; this does not mean it was routed into a human review desk. The patch excludes all later 4A.8K/M/N/O/P development changes and does not alter city queue policy, sending, MX, or V1/V2.

补丁不会创建 lead、邮箱、SAFE/发送资格、审核台项目或发送计划。`identity_review` 仍可从 `lead_discovery_results` 审计字段查询；这不代表记录已进入人工审核台。补丁不包含后续 4A.8K/M/N/O/P 开发改动，也不改变城市队列策略、发送、MX 或 V1/V2。
