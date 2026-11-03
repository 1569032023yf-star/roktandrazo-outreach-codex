# U1 服务原所有者配置 / Service original-owner configuration

固定源码 / Fixed source: 229c48c2d44cf18a12e9c6f9049d40847349e9ec | 2026-11-03T18:10:57.037585+00:00

实际接线：安装准备器从独立hash绑定的runtime plan提取original_owner_db，生成runtime.json并纳入supervisor的runtime_config_sha256；固定bootstrap将该引用传至宿主--original-owner-db。原owner与离线event_runtime互斥。准备器验证绝对规范路径、存在文件及reparse祖先；不复制、hash锁定或写入可变原数据库。
Implementation: installation preparation propagates original_owner_db from the separately hash-bound runtime plan into runtime.json and the supervisor runtime_config_sha256. The pinned bootstrap forwards it to the host --original-owner-db argument. Original-owner and offline event_runtime references are mutually exclusive. Preparation checks canonical absolute existing-file paths and reparse ancestors without copying, hash-locking or writing mutable database bytes.

验证 / Validation: python -B -m unittest test_u1_provision test_u1_host_runtime -q: 5 PASS, 5.188s. Actual PowerShell config generation verifies propagation, source bytes preserved and dual-authority rejection. Complete service bootstrap execution was not tested this round.

本SHA独审PENDING；全量NOT_RUN；安装包未重建，旧审核/包不继承。非完整发布验收。
Independent review PENDING for this SHA; full regression NOT_RUN; packages not rebuilt and previous reviews/archives not inherited. This is not complete release acceptance.

下一步 / Next: 通过完整固定bootstrap核验生成的服务配置，重建候选并独审；继续完成正式Provider及实测费用接线。
Validate the generated service configuration through the complete pinned bootstrap, rebuild the fixed candidate and obtain independent review; formal Provider and measured-cost integration remain required.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
未修改生产数据库、ACL或服务，未触发Inventory；复用WorkBuddy既有证据。
No production database, ACL or service changed; no Inventory triggered. Existing WorkBuddy evidence reused.
