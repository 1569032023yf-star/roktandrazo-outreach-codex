# SCM与Python启动接线 / SCM and Python startup integration

固定源码 / Fixed source: d1e613cdb64f957907812b87c5a0c867531c6d4f; base1b527d557674a4abd18a389c56851b6164c45dc5.

RoktU1Bridge now loads an optional supervisor.json (rokt.u1-supervisor.v1; exact8 string fields: schema,inventory_id,python,python_sha256,bootstrap,bootstrap_sha256,runtime_config,runtime_config_sha256). It pins and hashes the interpreter, standalone bootstrap and runtime config, creates Python suspended, assigns a KILL_ON_JOB_CLOSE Job Object, then resumes. No fallback outside Job Object exists. SCM stop terminates the job and checks ActiveProcesses==0 and parent termination; unexpected child exit fails the service process on its next heartbeat check (up to10s). 服务监督已接入源码，未安装或启动服务；不存在配置时保留禁用心跳候选行为。

Standalone bootstrap resolves active.json, verifies manifest and every packaged file before importing the pinned Python runtime. It rejects unmanifested files and reparse/hardlink files; runtime configuration requires original Inventory1784775229336 and dispatch/cancel/SMTP=false. 配置schema为rokt.u1-python-runtime.v1，要求release_root/state_root/token_file/credential_expires_at/snapshot/snapshot_sha256及三个false安全字段。凭据由既有授权机制提供，不生成、不输出。

Actual Windows harness compiled against the real service PE: started child+grandchild under Job, disposed supervisor and independently checked both processes terminated; wrong bootstrap hash rejected before child effect. Final36 tests PASS11.384s. 首轮测试遇到GBK输出线程解码异常，已改为显式UTF8容错后复测；该异常未隐藏为正式验收。Initial packageee65281 failed HOST_MISSING because namespace packages need no __init__.py; fixedd1e613c rebuilt and passed actual59-file package resolution, tamper rejection and first-install rollback. 失败与修复保留在INTEGRATION.json，未改写旧证据。

安装候选 / Install candidate: fixed-package/install.zip SHA256 fcc2df3e4475179ee216ac5c7de493c2f6faf47b08e1b92a7f3831053bf8baf7.
回滚工具 / Rollback tools: fixed-package/rollback-tools.zip SHA256 02c91a8beb7692b342be30360c14eb296ef06d5443728b66f6a3daa9d4330554.
Manifest 40200f7f9ee1022c6c7566dd8dfb11aaa1e0192cc292c95267ba57432ca78968. Full rollback also requires preserved STORE/versions and STORE/backups, not tools alone. 完整旧版本与切换记录必须共同保留。

Remaining: optional supervisor configuration provisioning and installer readback, independently approved ACL/runtime dependency closure, formal backend and original Inventory durable claim/lock connection, SCM recovery policy and unattended acceptance. No service-start/boot/logoff/crash acceptance is claimed by a local native harness. C# pins3 entry files, not every Python DLL/dependency; bootstrap verification does not exclude hostile changes after hashing, so trusted ACL/Inventory exclusion remain gates. Pending version activation must drain the current host; no hot switch/replay. 版本升级与正式Inventory互斥尚未完成，不把发布器锁当作生产锁。

Next code work: installer provisions exact disabled supervisor/runtime configs and verifies paths/hashes, then wire bounded backend execution through existing durable Slot/GrowthLedger/CancellationJournal and original Inventory admission. 冻结范围，继续代码接线，不追加检查器测试空转。Reuse consumed WorkBuddy13d061a/existing Issue2 receipt6561646296, no duplicate request or collection.

Independent review PENDING; no independent reviewer result available. Tests are author validation, not independent PASS. Production DB, SMTP, Inventory and services unchanged; no production8791 bind, no manual collection. 四总体状态 / Overall: DEVELOPMENT_COMPLETE=false;RELEASE_READY=false;PRODUCTION_DEPLOYED=false;PRODUCTION_ACCEPTED=false;BUSINESS_GROWTH=UNKNOWN.
