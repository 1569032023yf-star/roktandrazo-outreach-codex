# U1 直接归档构建修复 / Direct archive delivery fix

中文：固定源码fe51fbd05ed17eee727a25e2cd3a7b3430643249将完整运行时载荷直接写入排他创建的install.zip，取消重复的逐文件持久化安装中间树。仍两次读取来源并逐文件核对SHA256、检查命名空间和大小上限，最后写manifest并flush/fsync。来源变化停止并保留失败归档，已有路径拒绝覆盖。回滚组件从安装归档精确字节提取。此改动仅构建，不安装或开启任何门禁。
English: Fixed sourcefe51fbd05ed17eee727a25e2cd3a7b3430643249 streams the complete runtime payload into exclusively created install.zip, eliminating the duplicate per-file durable staging tree. It retains two-pass source SHA256 checking, namespace/size limits, manifest completion and final flush/fsync. Changed sources stop and preserve the failed archive; existing paths cannot be overwritten. Rollback components consume exact archive bytes. This changes packaging only and opens no installation or dispatch gates.

中文：22项定向通过，覆盖来源变化、已有归档拒绝、manifest与归档对应、旧发布生命周期及传统工程包兼容性。真实构建600秒超时，只有部分ZIP，BUILD.json和完整回滚归档不存在；未启动独立解压核验。848项全量37FAIL/17ERROR与基线ID相同，无新增，但不是全绿。详见下列真实JSON；PENDING不能继承旧候选成绩。Windows实际安装、注销、Session0、业务回执和费用均未验收，独审PENDING。所有最终状态false；BUSINESS_GROWTH=UNKNOWN。
English:22 targeted checks pass, covering changed-source preservation, existing-archive refusal, manifest/payload parity, release lifecycle and legacy delivery compatibility. The actual build timed out at600 seconds with a partial ZIP; BUILD.json and a complete rollback archive are absent. Independent extraction was not started. The848 regression retains37 failures/17 errors with unchanged IDs; it is not green. Observed evidence follows; PENDING never inherits earlier candidate results. Real Windows installation, logout, Session0, business receipts and costs remain unaccepted; independent review is PENDING. All final statuses are false; BUSINESS_GROWTH is UNKNOWN.

中文：沿用09:35:30至10:20:30的本轮窗口，新构建子进程上限600秒；最多两条重型线。未配置平台整轮硬超时。此前900秒超时产物完整保留。
English: The cycle remains09:35:30–10:20:30, with a600-second bound for the new build and at most two heavy workstreams. No platform whole-cycle hard timeout is configured. Previous900-second partial outputs remain preserved.

```json
{
  "updated_at": "2026-11-05T02:17:16.988251+00:00",
  "source_commit": "fe51fbd05ed17eee727a25e2cd3a7b3430643249",
  "checkpoint": "autonomy/evidence/u1_direct_archive_20261105/REPORT.md",
  "targeted_tests": {
    "run": 22,
    "failures": 0,
    "errors": 0,
    "output": "TARGETED.txt"
  },
  "package": "UNKNOWN_INCOMPLETE_BUILD",
  "partial_package": {
    "outcome": "UNKNOWN_INCOMPLETE_BUILD",
    "observed_at": "2026-11-05T10:17:16.891761+08:00",
    "source_commit": "fe51fbd05ed17eee727a25e2cd3a7b3430643249",
    "path": "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-delivery-direct-fe51fbd",
    "free_bytes": 2603212800,
    "build_json_exists": false,
    "artifacts": {
      "install.zip": {
        "bytes": 12684858,
        "complete": false
      }
    },
    "preserve_partial": true
  },
  "build_termination": {
    "outcome": "UNKNOWN_TIMEOUT",
    "timeout_seconds": 600,
    "source_commit": "fe51fbd05ed17eee727a25e2cd3a7b3430643249",
    "elapsed_seconds": 600.0737754000002,
    "command": [
      "C:\\Users\\15690\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
      "-X",
      "utf8",
      "-B",
      "-m",
      "autonomy.build_u1_delivery",
      "--output",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-delivery-direct-fe51fbd",
      "--source-commit",
      "fe51fbd05ed17eee727a25e2cd3a7b3430643249",
      "--python-runtime",
      "C:\\Users\\15690\\Documents\\ChatGPT\\线下\\u1-runtime-32f0246",
      "--runtime-manifest-sha256",
      "5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e"
    ]
  },
  "regression": {
    "source_commit": "fe51fbd05ed17eee727a25e2cd3a7b3430643249",
    "baseline_source_commit": "11bf1f9da4c74d1653f3f491a8312b536992eff6",
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
  "next_action": "Implement source-bound resumable build phases and phase timing:600-second build reached partial ZIP but not manifest completion; preserve partial ZIP and do not consume it as an install package. Then finish fixed-package verification and independent review."
}
```
