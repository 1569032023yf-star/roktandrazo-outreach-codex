# Phase 4A 部署结果 / Deployment results

> 2026-09-10T02:29:18Z 更新：最终 MX/V2 验收通过，SAFE AFTER=1，调度仍暂停。以下待测描述保留为部署时历史；以 PHASE4A_FINAL_MX_ACCEPTANCE.md 为准。 / Update: final MX/V2 acceptance passed, SAFE AFTER=1, scheduling remains held. Pending descriptions below are deployment-time history; PHASE4A_FINAL_MX_ACCEPTANCE.md is authoritative.

## 状态 / Status

已部署批准的 Phase 3D 六文件补丁；一次生产 Inventory 已成功完成。调度保持暂停，最终 SAFE FSP 统计待安全审查授权，不可宣称全部验收完成。
The approved Phase 3D six-file patch is deployed and one production Inventory completed successfully. Scheduling remains held. Final SAFE FSP measurement awaits network approval; overall acceptance is not complete.

DEPLOYMENT_EXECUTED = true
DEPLOYMENT_RUN_ID = phase4a-prod-20260910T020401Z
APPROVED_COMMIT = f67c785031075b8f3a55b5a8ab5b07191dec5b6d
WINDOWS_DUPLICATE_TASKS_DISABLED = 2/2
DUPLICATE_ACTIVE_TRIGGER_COUNT = 0
ROLLBACK_READY = true
TARGET_HASH_MATCH = 6/6
FROZEN_FILES_CHANGED = 0
ENV_CHANGED = false
DB_SCHEMA_CHANGED = false
INVENTORY_RUN_PASS = true
PHASE4A_INVENTORY_VALIDATION_PASS = PENDING
PRODUCTION_REPLENISHMENT_DEPLOYED = true
SCHEDULING_RESUMED = false

## 回滚与精确制品 / Rollback and exact artifacts

最新回滚目录（生产根外且 Git 忽略）： / Current rollback directory (outside production and Git-ignored):
C:\Users\15690\Documents\ChatGPT\线下\roktandrazo-outreach-dev\_audit_quarantine\phase4a\phase4a-prod-20260910T020401Z

database/bd_leads.db 使用 SQLite online backup，integrity_check=ok。original_files 保存五个原文件；rollback_manifest.json 保存基线、目标、冻结、数据库和 .env SHA，未复制或打印 .env 内容。scheduler_inventory.json 保存暂停状态。9月9日旧备份保留，不用于本次回滚。
database/bd_leads.db is an online SQLite backup with integrity_check=ok. original_files contains five original files; rollback_manifest.json records baseline, target, frozen, database and .env hashes without copying or printing .env contents. scheduler_inventory.json records hold state. The September 9 backup remains archived and is not this deployment's rollback source.

所有发布制品逐字节比对批准 Git commit；bd_db.py 仅 git apply 选择性补丁，其余五文件按清单应用。两次目标/冻结/env哈希复核通过。未部署开发 guards、测试、报告或开发 DB。无迁移。
All package bytes were checked against the approved Git commit. bd_db.py used selective git apply; the other five files followed the manifest. Target/frozen/env hashes passed twice. No development guards, tests, reports or development DBs were deployed. No migration ran.

回滚方法：保持暂停，恢复 original_files 中五个原文件，将本次新增 discovery/website_resolver.py 移到隔离目录，验证 baseline SHA；数据库保留审计，恢复 DB 需另行明确批准。本次未回滚。
Rollback: keep holds, restore the five original files, move newly added discovery/website_resolver.py to quarantine, and verify baseline hashes. Preserve the DB for audit; DB restoration requires separate explicit approval. No rollback was executed.

## 单次 Inventory / Single Inventory

COMMAND = bd_orchestrator.py --stage inventory --live
RUN_ID = inventory:2026-09-10:dd837e24
STARTED_UTC = 2026-09-10 02:06:30
FINISHED_UTC = 2026-09-10 02:18:08
EXIT_CODE = 0
JOB_STATUS = completed

NY/Ithaca，Discovery seen=8、new_unique=0；website resolution=15，resolved=2、not_found=11、identity_review=2；staging processed=2、new leads=0。日志 BroadReady=34/30，不等于 SAFE FSP，不用于替代最终 V2/MX。
NY/Ithaca discovery saw eight existing results, zero new places. Website resolution processed 15: two resolved, 11 not found, two identity reviews. Staging processed two with zero new leads. Logged BroadReady=34/30 is not SAFE FSP and does not substitute for final V2/MX.

| 指标 / Metric | Before | After | Delta |
|---|---:|---:|---:|
| TOTAL_LEADS | 1069 | 1069 | 0 |
| WEBSITE_VERIFIED (staging official_match) | 8 | 10 | 2 |
| VISIBLE_FIRST_PARTY_EMAILS | 313 | 314 | 1 |
| FULL_EVIDENCE_RECORDS | 0 | 1 | 1 |
| V2_ELIGIBLE_UNSENT | 0 | 未测 / Pending | 未测 / Pending |
| SAFE_FSP_UNIQUE_ORGS | 0 | 未测 / Pending | 未测 / Pending |

## 商户复核 / Merchant review

| 商户 / Merchant | 结果 / Result |
|---|---|
| Instant Replay Sports | 官方证据关联已有 lead 1085 / Official evidence linked to existing lead 1085 |
| The Cornell Store | 官网解析成功但历史门禁阻断 / Website resolved, history gate blocked |
| The Outdoor Store | 未接受搜索返回的其他门店官网 / Other-store search results not promoted |
| Bev and Co | 不接受其他身份网站，保留人工复核 / Different-identity site not promoted, manual review retained |
| Autumn Leaves Used Books | 未找到官网，未提升邮箱 / No website found, no email promoted |
| One Green Horse | 无结果，未提升 / No result, no promotion |
| Gourdlandia | 无结果，未提升 / No result, no promotion |

共22条 staging 有变化（含 Discovery hit metadata），15个官网解析商户；唯一新增邮箱对应 Instant Replay Sports，requested_url=http://ithacainstantreplaysports.com，final_url=https://ithacainstantreplaysports.com/，HTTP=200，HTTP/TLS=true，email_source_type=official_page_visible。
Twenty-two staging records changed including discovery hit metadata, with 15 website-resolution merchants. The sole new email belongs to Instant Replay Sports with the above same-party requested/final URLs, HTTP=200, HTTP/TLS=true and official_page_visible source.

email = ithacainstantreplaysports@yahoo.com
fetched_at = 2026-09-10T02:17:28.952484+00:00
content_hash = c44dbf0f03495fdcbd76dcdbb5510b05078f10f1bf0f0dba323816cbcee73827
literal_visible_excerpt = Triphammer 607.277.7366 | The Rink 607.216.0056 ithacainstantreplaysports@yahoo.com IthacaInstantReplaySports@yahoo.com

完整字面片段保存在隔离 review.json / Full literal excerpt is retained in quarantined review.json.

NEW_DUPLICATE_LEADS = 0
NEW_DUPLICATE_ORGS = 0
GUESSED_EMAIL_PROMOTED = 0
THIRD_PARTY_EMAIL_PROMOTED = 0
DIRECTORY_AS_OFFICIAL_PROMOTED = 0
IDENTITY_MISMATCH_PROMOTED = 0
INVALID_HTTP_TLS_PROMOTED = 0

以上重复数为本次增量，不是抹去历史重复：leads 表相同非空 organization_key 的额外行数前后均34（可含同组织多门店）。未新建 lead；最终 SAFE 组织去重统计仍待完成。
Duplicate counts above are deployment deltas, not claims of historical cleanup: excess lead rows sharing nonempty organization_key remain 34 before and after (potentially multiple locations per organization). No leads were inserted. Final SAFE organization deduplication measurement remains pending.

保护表计数前后完全相同 / Protected table counts unchanged:
send_log=516; bounce_log=63; suppression_list=63; final_send_plan=587; send_authorizations=22; send_authorization_entries=163.
未调用 SMTP/IMAP/Outreach。未创建 live FSP 或发送授权。schema 前后完全相同。
No SMTP/IMAP/Outreach was invoked; no live FSP or send authorization was created. Schema is identical.

## 剩余阻塞 / Remaining blocker

安全审查两次拒绝验收后冻结 MX/V2 查询，按旧开发20商户限制解释授权；已证明实际96候选/91域名并说明本次Phase4A生产统计授权，仍被拒绝。未绕过，改为纯离线核验，V2/SAFE AFTER 为 null，不伪报0。
Safety review twice rejected post-run frozen MX/V2 under the older 20-merchant development scope. Actual size (96 candidates/91 domains) and Phase 4A production measurement authorization were supplied, but denial persisted. No bypass occurred; offline verification records null V2/SAFE AFTER, not a fabricated zero.

需 Ian 明确授权针对本次生产验收向既有 MX Worker/公开 DNS 查询这91个公开域名，仅传域名，不传邮件正文、收件人列表或凭据到新端点。只完成查询，不再次 Inventory，不发送，不恢复调度。
Ian must explicitly authorize these 91 public-domain MX queries for production acceptance using the existing MX Worker/public DNS, transmitting only domains and no message bodies, recipient lists or credentials to new endpoints. Complete measurement only; no second Inventory, sending or scheduler resume.

Windows PreSend/Outreach 保持 DISABLED；WorkBuddy Inventory/PreSend/Preflight/Outreach 保持既有 PAUSED，未执行恢复。非重复 PostSend 与 Recovery Sync 未改动。
Windows PreSend/Outreach remain DISABLED. No WorkBuddy resume was performed; the four primary stages were PAUSED at precheck. Nonduplicate PostSend and Recovery Sync were left unchanged.
