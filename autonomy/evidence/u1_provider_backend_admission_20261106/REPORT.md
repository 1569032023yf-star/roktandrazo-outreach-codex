# U1 Provider backend admission / Provider 后端准入

实际工作目录 / Worktree: D:\CODEX\roktandrazo-workspace\u1-provider-backend-admission-20261106
分支 / Branch: codex/u1-provider-backend-admission-20261106
起点 / Base: 90ca1f9e57c32dbb77dda8ec1a0113f646b56bb1
固定源码 / Fixed source: 077967705772ef9fc994e6e30a49f7e647da99ba

修复：绑定 Provider 配置的 ProcessBackend 在写入 IN_FLIGHT 前校验完整业务请求及 Provider 一致性。缺失、非法、禁用或配置不匹配的请求不会启动子进程，也不会污染持久执行意图。通用离线 backend 保持原协议。
Fix: Provider-configured ProcessBackend validates the bound search request and configured Provider before durable execution intent. Invalid inputs launch no child and remain NOT_RECORDED. Generic offline backend retains its protocol.

验证 / Validation: 31 PASS, 10.082 seconds. Command: python -X utf8 -B -m unittest test_process_backend test_provider_worker test_provider_environment -v, under cooperating dev_cycle with 180-second child deadline. ROKT_DEV_ALLOW_LOOPBACK=1 permitted development loopback only. Five invalid-request cases prove no child/no intent; valid pinned input remains covered. Real Worker refusal remains durable UNKNOWN and cannot replay. No live Provider query was performed.

独审 / Independent review: PENDING; self-check is not independent approval. No new package, full regression, install or production acceptance is claimed. Provider authoritative cost and terminal receipt contracts remain CONTRACT_MISSING. Production gates unchanged: allow_install=false, allow_dispatch=false, allow_cancel_dispatch=false, SMTP=false; SerpAPI disabled.

主线与 canonical 未修改 / Main and local canonical queue unchanged: shared entrypoint adoption is not verified; this branch carries an isolated projection only. No global lock claim. Prior coordination/Job candidates remain review pending. Existing WorkBuddy evidence reused; no duplicate evidence request or receipt.

恢复 / Recovery: continue from fixed source and this report; review this candidate independently, validate shared entrypoints, then integrate under common mutex. Roll back isolated code by reverting 077967705772ef9fc994e6e30a49f7e647da99ba; no production installation was changed.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
