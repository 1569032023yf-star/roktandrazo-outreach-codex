# 离线日志读取绑定 / Offline journal inspection binding

实际开始 / Actual start: 2026-11-02T10:47:24.8479245+08:00. Base: 76d4bd0fa952d19e04adea6c90753a6d8fd83546. Source: c582ae72ea0b7de793aeaae81743913fdcd7cb71.

实现 / Implementation: inspector checks operation ID, manifest SHA256 and lease binding against the caller's expected values. It rejects malformed headers, duplicate JSON keys, non-object rows and excessive nesting. Reads are capped at 16385 bytes; logs over 16384 bytes return UNKNOWN with no partial-file digest. Driver passes its expected binding to final inspection. 检查操作、清单与租约头字段；拒绝畸形和超限日志，保留原字节，禁止自动重放。

验证 / Validation: 4 new tests; 18 focused PASS (1.001s); 125 combined PASS (6.672s). Source manifest pins Git blobs and working-byte SHA256 separately. 独审 / Independent review: PENDING. Old 833-test parity and old independent review do not certify this source. 本轮未执行全业务回归，旧结果不继承。

限制 / Limits: binding_verified only means header equality with caller input, not trusted lease authority or journal authenticity. A malformed body can remain UNKNOWN even when its header matches. Readback path identity is not held across close-to-open; I/O errors still propagate. 头绑定不是真实性、ACL或无人登录运行证明。No platform session-level hard timeout available; test subprocesses bounded at 120s; no service/task created.

生产证据 / Production evidence: WorkBuddy remote main remains 13d061a82568bc147efa689742a61b3e06d95a31; existing Issue #2 receipt 6561646296 is preserved without duplicate posting. 本轮未重新采样生产；canonical 本地队列实际读取，Git投影不是状态来源。8791 session-scoped and 7877 noninteractive/unattended acceptance remain blocked as previously recorded.

安全 / Safety: no production collection, deployment, database, SMTP, Windows service/task, ACL or proxy changes. Install, dispatch and cancel dispatch remain disabled. 生产派发关闭；未触碰其他工作树的未提交文件。

回滚 / Rollback: preserve evidence and use a reviewed offline revert to base 76d4bd0fa952d19e04adea6c90753a6d8fd83546 if required; never replay UNKNOWN operations or edit production journals. 本次无生产迁移或部署，Git保留源码备份。

下一项 / Next: close-to-read journal substitution and I/O error contracts, with readback identity verification; then pinned independent review. 正式身份、ACL、租约、backend与无人登录验收仍阻塞。

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
