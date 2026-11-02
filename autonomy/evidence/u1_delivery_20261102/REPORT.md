# U1实际交付增量 / U1 implementation delivery increment

固定源码 / Fixed source: fb6f667a1456a7d81e432e7cc87727697ef9fb9f. Base: f2a816a5eb992acc6ff92729a9ef7a9ea3ac2fa6. Scope frozen to file publishing and host integration, not further inspector-only work. 范围冻结为发布器与宿主实际集成，不再追加无交付价值的检查器测试。

## 实际代码 / Actual implementation

release_store.py implements first installation, new-file staging, upgrades, retained full version backups, atomic active-pointer commit, expected-current checks, rollback to previous version or ABSENT, and explicit inactive-version deletion. Active or backup-referenced versions cannot be deleted. Durable writes and an OS byte lock protect cooperating publishers. 首装与升级不要求目标文件已存在，旧版本原字节保留；回滚恢复完整旧文件集合，首次安装可回到未激活状态。目录不整树覆盖，生产数据库不纳入回滚。

u1_host_runtime.py composes the existing bearer-authenticated read-only HTTP handler with active-release validation and lifetime OS file locking. Credential is read from an externally provisioned file, never generated or logged here. No scheduler or execution route is created. Python宿主启动器已可运行，复用认证接口和恢复状态读取；进程退出释放锁，UNKNOWN结果不重放。

build_u1_delivery.py compiles the existing real RoktU1Bridge executable and packages pinned Git Python sources with release/rollback tools. 本次固定包含57个文件，不是伪PE或临时数据库替代品。

## 验收 / Validation

35 scoped tests PASS in5.368s. First 56-file package: real staged first installation, upgrade adding a new file, upgrade rollback and first-install rollback all passed. Final 57-file package: isolated subprocess imported installed Python bytes, served authenticated HTTP on an ephemeral loopback port and returned dispatch=false; first-install rollback passed. Exact records: INTEGRATION.json and FIXED_INTEGRATION.json. 定向测试服务于本次代码；未重复旧833项全量，不继承旧全量结论。

Install archive SHA256: b2e95728fd957b05a1b8ad0739f123a9165898b0cfa241213b57eafb35cf0a07.
Rollback-tools archive SHA256: d36936ed382f1e1536f6457fb99976925ee0efbb09fcbc49eb3ba9548fbee00d.
Manifest SHA256: a754ae2604c2584a09d4402b4915ada1bbd8b76f029732023fb8b233a48a87f8.

## 使用与边界 / Usage and boundaries

Candidate file publisher: `python -m autonomy.release_store --root STORE stage PACKAGE MANIFEST_SHA`; then `activate VERSION --expected-current ABSENT` for first installation, or exact previous version for upgrade. Save the returned transaction ID; rollback uses `rollback TRANSACTION --expected-current VERSION`. `status` verifies active content. `delete-inactive VERSION` refuses active/backup-referenced content. STORE must be a pre-created, trusted directory. 仅隔离目录已执行；生产服务安装尚未授权、未执行。

Full old version bytes live in STORE/versions; pointer transition records live in STORE/backups. Keep both to restore. The rollback-tools.zip contains executable rollback tooling, not production state or a standalone backup of installed versions. 回滚工具包不能替代现场完整版本备份，不能单独还原一台主机。

The active pointer is a new consumer contract: existing SCM installer still uses its old fixed directory and does not resolve it. RoktU1Bridge still only emits heartbeats; SCM-to-Python child supervision/Job Object, authenticated execution backend, original Inventory lock/claim integration, trusted ACL/maintenance exclusion and unattended recovery acceptance remain unfinished. 本次OS锁是发布器/宿主互斥，不是已接入正式Inventory的锁。No claim of complete host integration or complete service rollback.

Path checks reject traversal/reparse/hardlink files, but hostile concurrent namespace replacement is not excluded by these checks. Trusted destination ACL and Inventory exclusion require final integration/review. Real Python runtime remains an external dependency, not bundled/provisioned. Independent review is PENDING; author tests and self-review are not independent PASS. 未绕过Job Object/权限/网络门禁；未向用户重新索要WorkBuddy既有证据。

## 证据复用与下一步 / Evidence reuse and next step

Reuse consumed WorkBuddy13d061a82568bc147efa689742a61b3e06d95a31 and existing Issue2 receipt6561646296; no repeated collection/request/receipt. Existing production evidence is historical and does not certify this candidate. 优先把SCM固定目录启动改为经过核验的版本解析，并加入Python子进程Job Object监督；随后连接现有backend/持久slot/原Inventory1784775229336。冻结范围，只修交付阻断项。Final source review and approved installation gates precede any service installation/enabling.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
SMTP configuration unchanged; no production DB writes or collection by this work. 未创建第二Inventory、未安装/启动服务、未改变ACL或代理。
