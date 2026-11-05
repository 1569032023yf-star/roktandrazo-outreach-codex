# U1 固定宿主分阶段交付构建 / Pinned host phased delivery build

中文：固定源码将宿主准备与归档拆分。准备阶段固定完整CPython、依赖及AMD64桥接，输出source/manifest绑定的HOST_INPUT；它不是完整安装包。归档入口对固定宿主持有输入句柄，核对runtime清单绑定，在最终身份复核后才写BUILD.json。失败归档保留，恢复使用新的排他输出，绝不覆盖或消费旧partial ZIP。24项定向通过。实际运行、回归、归档与独立解压结果逐项记录如下，PENDING/UNKNOWN不视为通过。独审PENDING，正式Provider费用/回执合同缺失，Windows安装/注销/Session0未验收。
English: Fixed source separates host preparation from archive assembly. Preparation pins complete CPython, dependencies and the AMD64 bridge and emits source/manifest-bound HOST_INPUT; this is not a complete installer. Archive assembly holds prepared-host input handles, checks runtime-manifest binding and writes BUILD.json only after final identity revalidation. Failed archives are preserved; recovery uses a new exclusive output without overwriting or consuming partial ZIPs.24 targeted tests pass. Actual phase, regression, archive and extraction outcomes are recorded below; PENDING/UNKNOWN is not a pass. Independent review remains PENDING; formal Provider cost/receipt contracts and actual Windows installation/logout/Session0 acceptance remain outstanding.

中文：本轮10:39:03至11:24:03 +08；子进程有显式时限，平台整轮硬超时未配置。未安装服务或改动生产，所有安装/派发/取消/SMTP门禁关闭；旧失败产物完整保留。
English: Cycle10:39:03–11:24:03 +08; subprocess timeouts are explicit, with no configured platform whole-cycle hard timeout. No service installation or production mutation; installation/dispatch/cancel/SMTP gates remain closed. Previous failed outputs remain preserved.

```json
{
  "updated_at": "2026-11-05T03:01:02.181878+00:00",
  "source_commit": "373899370dcc55037c5f7f89654657a41389c56c",
  "checkpoint": "autonomy/evidence/u1_build_phases_20261105/REPORT.md",
  "targeted_tests": {
    "run": 24,
    "failures": 0,
    "errors": 0,
    "output": "TARGETED.txt"
  },
  "host_input": {
    "allow_install": false,
    "manifest_sha256": "03d6ed0388552e0c9d989d593d30b198fc56b8d963f9bd5cf60edd885adeca75",
    "package_complete": false,
    "phase": "HOST_READY",
    "prepared_host": "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-host-phase-3738993\\runtime-host",
    "runtime_manifest_sha256": "5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e",
    "source_commit": "373899370dcc55037c5f7f89654657a41389c56c"
  },
  "prepare_termination": {
    "outcome": "TERMINAL",
    "returncode": 0,
    "source_commit": "373899370dcc55037c5f7f89654657a41389c56c",
    "elapsed_seconds": 64.55881980003323,
    "command": [
      "C:\\Users\\15690\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
      "-X",
      "utf8",
      "-B",
      "-m",
      "autonomy.build_u1_delivery",
      "--source-commit",
      "373899370dcc55037c5f7f89654657a41389c56c",
      "--python-runtime",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-runtime-32f0246",
      "--runtime-manifest-sha256",
      "5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e",
      "--output",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-host-phase-3738993",
      "--prepare-only"
    ]
  },
  "package": "UNKNOWN_INCOMPLETE_BUILD",
  "archive_termination": {
    "outcome": "UNKNOWN_TIMEOUT",
    "timeout_seconds": 900,
    "source_commit": "373899370dcc55037c5f7f89654657a41389c56c",
    "elapsed_seconds": 900.0780086999875,
    "command": [
      "C:\\Users\\15690\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
      "-X",
      "utf8",
      "-B",
      "-m",
      "autonomy.build_u1_delivery",
      "--source-commit",
      "373899370dcc55037c5f7f89654657a41389c56c",
      "--python-runtime",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-runtime-32f0246",
      "--runtime-manifest-sha256",
      "5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e",
      "--output",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-delivery-phased-3738993",
      "--prepared-host",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-host-phase-3738993\\runtime-host",
      "--prepared-host-manifest-sha256",
      "03d6ed0388552e0c9d989d593d30b198fc56b8d963f9bd5cf60edd885adeca75"
    ]
  },
  "regression": {
    "source_commit": "373899370dcc55037c5f7f89654657a41389c56c",
    "baseline_source_commit": "fe51fbd05ed17eee727a25e2cd3a7b3430643249",
    "run": 848,
    "failures": 37,
    "errors": 17,
    "baseline_result_sha256": "4b317842b6b693677511ce888e4da0a9196aec8d9841435555cdf8bfe8484190",
    "candidate_result_sha256": "4b317842b6b693677511ce888e4da0a9196aec8d9841435555cdf8bfe8484190",
    "new_failures": [],
    "resolved_failures": [],
    "new_errors": [],
    "resolved_errors": []
  },
  "extracted_verification": "PENDING",
  "verify_termination": "PENDING",
  "independent_review": "PENDING",
  "provider_contract": "CONTRACT_MISSING",
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
  "next_action": "Use the existing prepared-host input handles for archive reads without repeated ancestor path queries, retaining per-file digest, identity and final revalidation. The900-second archive attempt is incomplete and must not be consumed. Then finish fixed-package extraction verification and independent review."
}
```

中文：实测宿主准备64.56秒成功；安装归档于870.996秒完成，900秒上限在回滚工具阶段触发。BUILD.json缺失，最终固定输入复核与完整回滚归档未确认；即使install.zip可打开，也不可作为正式完整包消费。
English: Host preparation completed in64.56 seconds; install archive assembly completed at870.996 seconds. The900-second timeout occurred during rollback tools. BUILD.json is absent; final pinned-input revalidation and complete rollback archive remain unconfirmed. An openable install ZIP is not an accepted complete delivery.
