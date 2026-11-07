# 正式启动预检与输入准入 / Startup preflight and input admission

Task: rokt-razo-20261107T151008Z; start: 2026-11-07T23:10:22.3981372+08:00; checkpoint: 2026-11-07T15:22:32.374942+00:00.
Workdir: D:\CODEX\roktandrazo-workspace\u1-startup-preflight-20261107; branch: codex/u1-startup-preflight-20261107; Git 2.54.0.windows.1.
Start SHA: 5b4e7b441a476e5b24e7fcd9ebeb83c7a2ba23cf; fixed source: d43209c01e8ec21da578b62c0b6c9de2b0850399.

中文：真实宿主此前只在后续恢复查询检查快照摘要，并允许过期凭据启动监听。本轮在打开原Inventory引用、持久状态或监听前检查凭据有效期、令牌格式与快照实际字节摘要。独立bootstrap拒绝重复JSON键、相对运行路径及不合法快照摘要。
English: The real host previously deferred snapshot digest checks to recovery requests and could listen with expired credentials. Startup now checks expiry, token shape and snapshot byte digest before original-owner references, persistent state or listener creation. The standalone bootstrap rejects duplicate JSON keys, relative runtime paths and invalid snapshot digests.

中文：接入真实只读入口：用包内Python -I -B执行service/u1_bootstrap.py <绝对runtime配置路径> --preflight，进入正式宿主参数路径，验证固定发布与现存状态目录，不创建锁/事件数据库、不绑定8791、不连接生产数据库、不发请求。输出明确区分字节/清单验证与未验证的快照schema、原Inventory权威和活锁；后者均false，不能据此安装或派发。
English: The packaged Python -I -B service/u1_bootstrap.py <absolute runtime configuration> --preflight now follows the real host argument path. It validates release integrity and existing state directories without creating locks/event databases, binding8791, connecting production databases or sending requests. Byte/manifest checks remain separate from unverified snapshot schema, Inventory authority and live lock; the latter stay false and cannot authorize installation/dispatch.

中文：24项定向及组合验证通过，12.679秒。重新构建固定源码真实CPython禁用包；5058文件摘要通过，4960宿主回滚组件与安装内容逐字节一致。五项包内探针和最终完整性VERIFIED；新增真实bootstrap→宿主preflight及全树字节前后不变检查。未继承旧833测试；未执行正式安装/回滚或注销重启。
English:24 targeted/combined checks passed in12.679s. A fresh fixed-source real-CPython disabled package contains5058 verified digests and4960 identical host rollback components. Five packaged probes plus final integrity VERIFIED, including actual bootstrap-to-host preflight and before/after file-tree equality. No old833-test result inherited; no formal installation, rollback, logout or reboot performed.

Install ZIP SHA256: 306c4247ac0e3cc680261b2f46aea919b7623c3207525f4031c9d583f884d2c2
Rollback ZIP SHA256: 3c52463bf17d56de228c44b1364a14d86c5d78e0cf2e6ff3fc01ccd113e6bbd7
Manifest SHA256: ee9544cd5a93bcdf5144b800b1c4b8d31dc647f2b096600fd44d693bde82e169

中文：初次prepare命令缺branch在启动前被拒绝，已修正；归档比较首次漏host/成员前缀，已修正验证器并全量摘要通过，包未修改。完整受控运行回执随报告保存。
English:An initial prepare invocation without branch was rejected before child start and corrected. Initial archive comparison omitted the host/ member prefix; correcting the verifier yielded all digests passing, with no package changes. Controlled run receipts are preserved.

中文：独审PENDING，没有可用独立Reviewer，未以自检替代。main/远端仍03c2ec44e1ca4d8b1b8d10841756ded13380f571；canonical可读但未改，多聊天共同入口协调尚未证明。仅更新隔离投影/checkpoint并推送独立分支。C旧路径Junction指向D已复核，备份未动。受控子进程期限180/240/300/600秒；不声称全局锁或整轮平台硬超时。
English:Independent review PENDING; self-check is not independent review. Main/remote remains03c2ec44e1ca4d8b1b8d10841756ded13380f571. Canonical is readable but unchanged because shared cross-chat entry adoption remains unproven; only isolated projection/checkpoint is updated and the independent branch pushed. C-to-D Junction rechecked; backups untouched. Controlled child deadlines180/240/300/600s do not establish a global lock or whole-chat platform cutoff.

中文：DEVELOPMENT_COMPLETE=false；RELEASE_READY=false；PRODUCTION_DEPLOYED=false；PRODUCTION_ACCEPTED=false；BUSINESS_GROWTH=UNKNOWN。allow_install/allow_dispatch/allow_cancel_dispatch/SMTP均false，SerpAPI未启用。Provider权威费用/币种/终态/取消回执仍CONTRACT_MISSING。下一步：快照schema及Worker业务启动导入/参数闭环、累计固定候选独审，共同协调确认后主线集成。
English:Overall development/release/deployment/acceptance false; business growth UNKNOWN. Installation/dispatch/cancel/SMTP remain false; SerpAPI stays disabled. Authoritative Provider cost/currency/terminal/cancellation receipts remain CONTRACT_MISSING. Next: snapshot schema and Worker import/argument closure, independent review of the cumulative fixed candidate, then coordinated main integration.
