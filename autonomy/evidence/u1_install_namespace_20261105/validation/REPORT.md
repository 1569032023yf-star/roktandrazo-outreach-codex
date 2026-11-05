# U1 固定发布候选 / Fixed delivery candidate

中文：固定源码11bf1f9da4c74d1653f3f491a8312b536992eff6将发布器普通路径检查改为每级一次不跟随的lstat，保留reparse、权限错误及身份门禁；同时验证此前安装输入命名空间冲突优化。未缓存祖先，也未放宽TOCTOU检查。
English: Fixed source11bf1f9da4c74d1653f3f491a8312b536992eff6 removes redundant metadata probes using one no-follow lstat per ancestor. Reparse, access-error and identity gates remain; no ancestor cache or TOCTOU relaxation was introduced. Previous installer namespace optimization was also validated.

中文：20项定向通过。最终源码独立848项全量仍37FAIL/17ERROR，新增/消除失败及错误ID均为空，不是全绿。旧21568c8包复核600秒超时，最终完整性UNKNOWN，不能继承已通过的局部探针。
English:20 targeted checks pass. The final-source independent848 regression retains37 failures/17 errors with no added/resolved IDs; it is not green. The old21568c8 package recheck timed out at600 seconds; final integrity is UNKNOWN and partial probes do not establish acceptance.

中文：首次测试因symlink权限WinError1314失败，改用临时junction验证悬空reparse后通过；未提权。隔离回归树的本轮误截断.development-copy先保存diff，仅恢复该文件。所有历史包与他人文件保留。
English: The initial symlink fixture failed with WinError1314. A temporary dangling junction then verified reparse rejection without elevation. The accidentally truncated development marker in the isolated regression tree was restored only after preserving its diff. Historical packages and other work remain preserved.

中文：新构建900秒超时；runtime-host4960文件完成、install部分3360文件，BUILD.json及两个归档均不存在。没有启动新包解压核验。部分目录保留，下一步修复有界可恢复的载荷分阶段构建，不盲目重建。详见下方原始JSON和同目录输出。回滚工具不是现场备份，也不是实际回滚验收。正式Provider费用/终态合同缺失，独审PENDING。未安装、派发、真实采集或发信；SerpAPI关闭。所有最终状态false，BUSINESS_GROWTH=UNKNOWN。
English: The new build timed out at900 seconds: runtime-host has4960 files and partial install has3360; BUILD.json and both archives are absent. No new-package extraction was run. Preserve partial output and fix bounded resumable payload staging instead of blindly rebuilding. Observed evidence follows below and in adjacent raw outputs. Rollback tools are neither site backups nor actual rollback acceptance. Authoritative Provider cost/terminal contracts remain missing and independent review is PENDING. No install, dispatch, collection or email occurred; SerpAPI remains disabled. All final states are false; BUSINESS_GROWTH is UNKNOWN.

中文：本轮09:35:30启动、10:20:30截止；无平台整轮硬超时字段，子进程设置有界超时，最多两条重型线。唯一下一动作以STATUS.json为准。
English: This cycle starts09:35:30 and ends10:20:30. No platform whole-cycle hard-timeout field is available; subprocesses are bounded, with at most two heavy workstreams. STATUS.json records the next action.

```json
{
  "updated_at": "2026-11-05T02:02:51.743881+00:00",
  "source_commit": "11bf1f9da4c74d1653f3f491a8312b536992eff6",
  "checkpoint": "autonomy/evidence/u1_install_namespace_20261105/validation/REPORT.md",
  "targeted_tests": {
    "command": "python -X utf8 -B -m unittest test_release_store test_install_inputs test_delivery_verification -v",
    "run": 20,
    "failures": 0,
    "errors": 0
  },
  "full_regression": {
    "source_commit": "11bf1f9da4c74d1653f3f491a8312b536992eff6",
    "baseline_source_commit": "21568c8267d7d20b3127eab8d3f5c866202868fd",
    "run": 848,
    "failures": 37,
    "errors": 17,
    "new_failures": [],
    "new_errors": [],
    "resolved_failures": [],
    "resolved_errors": [],
    "baseline_result_sha256": "4b317842b6b693677511ce888e4da0a9196aec8d9841435555cdf8bfe8484190",
    "candidate_result_sha256": "4b317842b6b693677511ce888e4da0a9196aec8d9841435555cdf8bfe8484190"
  },
  "package": "UNKNOWN_INCOMPLETE_BUILD",
  "build_termination": {
    "outcome": "UNKNOWN_TIMEOUT",
    "timeout_seconds": 900,
    "command": [
      "C:\\Users\\15690\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
      "-X",
      "utf8",
      "-B",
      "-m",
      "autonomy.build_u1_delivery",
      "--output",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-delivery-publisher-11bf1f9",
      "--source-commit",
      "11bf1f9da4c74d1653f3f491a8312b536992eff6",
      "--python-runtime",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-runtime-32f0246",
      "--runtime-manifest-sha256",
      "5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e"
    ],
    "elapsed_seconds": 900.089
  },
  "partial_package": {
    "observed_at": "2026-11-05T10:02:30.202738+08:00",
    "package_path": "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-delivery-publisher-11bf1f9",
    "source_commit": "11bf1f9da4c74d1653f3f491a8312b536992eff6",
    "free_bytes": 2059358208,
    "build_json_exists": false,
    "install_zip_exists": false,
    "rollback_zip_exists": false,
    "outcome": "UNKNOWN_INCOMPLETE_BUILD",
    "preserve_partial": true,
    "subtrees": {
      "runtime-host": {
        "files": 4960,
        "bytes": 239197439
      },
      "source-files": {
        "files": 97,
        "bytes": 1110004
      },
      "install": {
        "files": 3360,
        "bytes": 160076026
      }
    }
  },
  "extracted_verification": "NOT_RUN",
  "verification_termination": null,
  "old_integrity": {
    "package_source_commit": "21568c8267d7d20b3127eab8d3f5c866202868fd",
    "verifier_source_commit": "1bf8d59aa1d9ce8ecb78da6590626bcf4380962f",
    "outcome": "UNKNOWN",
    "checks": [],
    "allow_install": false,
    "allow_dispatch": false,
    "smtp_enabled": false,
    "package_complete": false,
    "independent_review": "PENDING",
    "runtime_probes_repeated": false,
    "active_phase": "FINAL_OUTER_REVALIDATION",
    "elapsed_seconds": 571.287,
    "archive_sha256": "32cb4b3676d2c5b38e63fec0b0bd4516cc13f86d76c6021463df3d137e062720",
    "parent_driver_timeout": true,
    "final_integrity_verified": false
  },
  "independent_review": "PENDING",
  "provider_contract": "CONTRACT_MISSING",
  "rollback_verified": false,
  "allow_install": false,
  "allow_dispatch": false,
  "allow_cancel_dispatch": false,
  "smtp_enabled": false,
  "statuses": {
    "DEVELOPMENT_COMPLETE": false,
    "PACKAGE_COMPLETE": false,
    "PROVIDER_ACCEPTED": false,
    "WINDOWS_ACCEPTED": false,
    "RELEASE_READY": false,
    "PRODUCTION_DEPLOYED": false,
    "PRODUCTION_ACCEPTED": false,
    "BUSINESS_GROWTH": "UNKNOWN"
  },
  "cycle": {
    "start": "2026-11-05T09:35:30+08:00",
    "cutoff": "2026-11-05T10:20:30+08:00",
    "platform_hard_timeout": false,
    "max_heavy_workstreams": 2
  },
  "next_action": "Instrument and fix bounded resumable install-payload staging: the 900-second build stopped with3360 of5057 files and no archives. Preserve the partial directory; do not blindly rerun. Then resume fixed-package verification and original-owner business integration. Independent review remains PENDING."
}
```
