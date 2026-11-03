"""同步实际交付状态 / Synchronize evidenced delivery state; gates stay closed."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SOURCE='68788653c848659c63f85021075fedee4aca5b13'


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    tests=load(HERE/'validation/TARGETED.json')
    comparison=load(HERE/'comparison/COMPARISON.json')
    review=load(HERE/'review-6878865/INDEPENDENT_RESULT.json')
    artifact_review=load(HERE/'review-6878865/INDEPENDENT_PACKAGE_RESULT.json')
    package=load(HERE/'package/BUILD.json');owner_package=load(HERE/'OWNER_PACKAGE.json')
    assert all(v['source_commit']==SOURCE for v in (tests,review,artifact_review,package,owner_package))
    assert comparison['candidate_commit']==SOURCE and comparison['complete']
    assert tests['passed'] and review['status']=='OFFLINE_SCOPED_REVIEW_PASSED'
    package=dict(package,independent_review=artifact_review['status'],
                 review_evidence='review-6878865/INDEPENDENT_PACKAGE_RESULT.json')
    now=datetime.now(timezone.utc).isoformat()
    next_zh='完成正式Provider/backend协议与原stage入口、服务事件消费者的固定调用链；保留原唯一Inventory、持久事件/claim/费用/取消和结算合同。当前原owner身份适配器仍使用isolated_offline协议，不是正式Provider接线完成。完整候选审核和授权后再做隔离Windows首装、升级、中断恢复及回滚验收。'
    next_en='Complete the fixed call chain connecting the formal Provider/backend protocol, original stage entry and service event consumer, retaining the sole original Inventory and durable event/claim/cost/cancellation/settlement contracts. The current original-owner adapter still uses the isolated_offline protocol and does not complete formal Provider wiring. After complete-candidate review and authorization, perform isolated Windows first-install, upgrade, interruption recovery and rollback acceptance.'
    record=dict(source_commit=SOURCE,updated_at=now,report=HERE.relative_to(ROOT).as_posix()+'/REPORT.md',
        tests=tests,independent_review=review['status'],independent_tests=review['independent_tests'],
        independent_review_scope='Original-owner identity/event/claim/settlement adapter; not complete release acceptance',
        current_full_regression=comparison,current_package=package,owner_package=owner_package,
        original_owner_identity_event_adapter_integrated=True,original_stage_event_consumer_connected=False,
        original_owner_release_requires_captured_incarnation=True,old_receipt_cross_owner_rejected=True,
        formal_backend_integrated=False,formal_maintenance_integrated=False,installable_release=False,
        development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,
        allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,
        inventory_id='1784775229336',next_action=next_en,next_action_zh=next_zh)
    save(HERE/'RESULT.json',record)
    source=[]
    for name in subprocess.check_output(['git','diff','--name-only','4b0353cbc4a5c69998fdd597d2bb884f7f5da8d0',SOURCE],cwd=ROOT,text=True).splitlines():
        if not name.endswith('.py') or '/evidence/' in name:continue
        blob=subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT)
        actual=(ROOT/name).read_bytes()
        assert blob.replace(b'\r\n',b'\n')==actual.replace(b'\r\n',b'\n')
        source.append(dict(path=name,git_blob_sha256=hashlib.sha256(blob).hexdigest(),actual_sha256=hashlib.sha256(actual).hexdigest()))
    save(HERE/'SOURCE_MANIFEST.json',dict(source_commit=SOURCE,files=source))
    for rel in ('autonomy/AUTONOMOUS_TASK_QUEUE.json','autonomy/runtime/queue.json'):
        path=ROOT/rel;value=load(path)
        task=next(t for t in value['tasks'] if t['id']=='A-unattended-architecture-20261026')
        task.update(candidate_commit=SOURCE,status='in_progress',updated_at=now,checkpoint=record['report'],
            targeted_tests=tests['tests_run'],review_status=review['status'],full_regression=comparison,
            u1_original_owner_session_latest=record,next_action=next_en,next_action_en=next_en,next_action_zh=next_zh)
        value.update(u1_original_owner_session_latest=record,checkpoint=record['report'],updated_at=now)
        save(path,value)
    report=f'''# U1 原所有者会话接线交付 / Original-owner session integration delivery

固定源码 / Fixed source: `{SOURCE}` | {now}

## 实际工程 / Implemented engineering

中文：原bd_db取锁事务现在同时持久化PID创建身份、随机nonce及原数据库路径/文件身份。原stage捕获取锁事务返回的会话凭据，释放必须同事务匹配该凭据；旧finally、同holder重用及死进程不能释放新会话。服务host可用受信只读原DB连接工厂观察原owner，HTTP不接收DB路径、PID或权利来源。OriginalOwnerSlotAdapter复用原slot、预算与签名验证，不创建supervisor锁或新调度器。

English: The original bd_db acquisition transaction now persists process creation identity, random nonce and original-database path/file identity. The original stage captures the transaction's capability; release matches that capability in the same transaction, preventing stale finally blocks, reused holders and dead processes from releasing a new incarnation. The host can observe the original owner through a trusted read-only DB connection factory; HTTP accepts no DB path, PID or authority source. OriginalOwnerSlotAdapter retains existing slot, budget and signature checks without creating a supervisor lock or scheduler.

中文：原DB事件intent在HTTP之前落盘，回包丢失不得换事件重试；预算和slot claim之后、backend之前持久化精确claim关联。operation及两种受信收据均绑定当前owner、事件和claim摘要。结算失败保持树unverified和原锁，禁止新日期执行与安装维护取权。取消日志拒绝占用三个受保护数据库及其SQLite保留侧文件。全部动作仅在开发源码、临时数据库及隔离回环测试完成。

English: Original-DB event intent precedes HTTP; a lost response cannot authorize another event. After budget/slot claim and before backend invocation, the exact claim join is persisted. Operations and both authenticated receipts bind the current owner, event and claim digests. Failed settlement retains an unverified tree and original lock, blocking a new business date and installation maintenance. Cancellation journals cannot occupy protected databases or SQLite sidecars. All actions used development source, temporary databases and isolated loopback tests.

## 测试及独审 / Tests and independent review

- 当前固定组合 / Current fixed-candidate combined suite: {tests['tests_run']} PASS, {tests['seconds']}s; failures={len(tests['failures'])}, errors={len(tests['errors'])}, skips={len(tests['skips'])}.
- 独立范围审核 / Independent scoped review: {review['status']}; {review['independent_tests']['count']} PASS, {review['independent_tests']['duration_seconds']}s. 两P1及侧文件缺口已修复；修复前诊断原样保留。 / Both P1 findings and the sidecar gap were repaired; pre-fix diagnostics are retained.
- 额外探针 / Additional probes: claim关联提交前后丢ACK均0 backend调用、禁止释放及重放；真实进程os._exit(29)保留封锁；20轮事件intent/释放竞争没有双成功。独审记录20次均释放先赢，不声称随机探针覆盖两种调度顺序。 / Lost ACK before/after claim-join commit yields zero backend calls and denies release/replay; actual os._exit(29) preserves exclusion; 20 intent/release races had no dual success. The independent report records release winning all 20 runs, without claiming both scheduling orders were randomly observed.
- 可比全量 / Comparable full regression: baseline `{comparison['baseline_commit']}` / candidate `{SOURCE}`: {comparison['baseline_run']} / {comparison['candidate_run']} tests; failures {comparison['baseline_failures']} / {comparison['candidate_failures']}; errors {comparison['baseline_errors']} / {comparison['candidate_errors']}. NO_NEW_REGRESSION={comparison['no_new_regression']}; ALL_GREEN={comparison['all_green']}。未继承旧SHA结果，不宣称全绿。 / Old-SHA results are not inherited; no all-green claim.

## 制品 / Artifacts

真实AMD64宿主已重新编译，{package['files']}载荷文件；另附八文件原所有者依赖包，fresh Python -I仅导入验证通过。每个文件摘要见ARTIFACT_MANIFEST.json；独立制品审核见review-6878865。外部CPython未捆绑。原Publisher源码未改变，本轮不将旧Publisher包冒充新SHA包。

The actual AMD64 host was rebuilt with {package['files']} payload files. The separate eight-file original-owner dependency archive passed a fresh Python -I import-only check. ARTIFACT_MANIFEST.json records every file digest; see review-6878865 for independent artifact checks. External CPython is not bundled. Publisher source is unchanged; an old Publisher archive is not relabeled as this candidate.

- install.zip SHA256: `{package['artifacts']['install.zip']}`
- rollback-tools.zip SHA256: `{package['artifacts']['rollback-tools.zip']}`
- Host manifest SHA256: `{package['manifest_sha256']}`
- owner-companion.zip SHA256: `{owner_package['artifact_sha256']}`
- Owner manifest SHA256: `{owner_package['manifest_sha256']}`

## 尚未完成及现场门禁 / Remaining work and site gates

{next_zh}

{next_en}

中文：原stage目前仅接入会话捕获与释放核验，尚未改成正式服务事件调用入口；实际HTTP端到端测试由隔离现有owner进程消费，业务backend/费用收据为受信测试替身。不能将该测试当真实Provider执行或完整可安装版本。真实PowerShell/SCM/ACL成功路径、Windows首装/升级/安装与回滚中断及无人值守周期仍需完整候选和授权后验收；不重复索要WorkBuddy已交P1证据，不绕过执行策略。

English: The original stage currently captures and validates the owner capability at release; it is not yet the formal service-event entry. Actual HTTP end-to-end tests consume from an isolated existing-owner process, with business backend/cost receipts supplied by trusted test doubles. This does not prove real Provider execution or a complete installable release. Successful real PowerShell/SCM/ACL paths, Windows first install/upgrade/install and rollback interruption, and unattended cycles still require a complete candidate and authorization. Existing WorkBuddy P1 evidence is reused; execution policy is not bypassed.

中文：WorkBuddy下一步只需针对最终完整SHA核验Disabled/Stopped、非对称ACL、精确文件所有权、维护权持续持有、故障恢复以及唯一Inventory排他；当前不要求安装或现场写入。

English: WorkBuddy should later verify Disabled/Stopped state, asymmetric ACLs, exact file ownership, continuous maintenance authority, fault recovery and sole-Inventory exclusion against the final complete SHA. No installation or site writes are requested now.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`
'''
    (HERE/'REPORT.md').write_text(report,encoding='utf-8')
    brief=f'''# U1 原所有者会话当前状态 / Original-owner session checkpoint

固定源码 / Fixed source: `{SOURCE}` | {now}

中文：原DB owner身份、HTTP事件intent、持久claim及收据结算适配器已接线；两P1独审问题已关闭。组合{tests['tests_run']}项通过，范围独审{review['independent_tests']['count']}项通过。可比全量基线与候选各{comparison['candidate_run']}项，分别{comparison['baseline_failures']}/{comparison['candidate_failures']} failures及{comparison['baseline_errors']}/{comparison['candidate_errors']} errors；ALL_GREEN={comparison['all_green']}，NO_NEW_REGRESSION={comparison['no_new_regression']}。

English: Original-DB owner identity, HTTP event intent, durable claim and receipt-settlement adapters are connected; both independent P1 findings are closed. Combined suite: {tests['tests_run']} passed. Independent scoped suite: {review['independent_tests']['count']} passed. Comparable baseline/candidate each ran {comparison['candidate_run']} tests, with {comparison['baseline_failures']}/{comparison['candidate_failures']} failures and {comparison['baseline_errors']}/{comparison['candidate_errors']} errors; ALL_GREEN={comparison['all_green']}, NO_NEW_REGRESSION={comparison['no_new_regression']}.

{next_zh}

{next_en}

工程包摘要、每项结果和审核范围 / Engineering archive digests, individual results and review scope: [{record['report']}](../u1_original_owner_session_20261103/REPORT.md).

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
'''
    for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
        (ROOT/'autonomy/evidence/unattended_20261026'/name).write_text(brief,encoding='utf-8')
    manifest_path=ROOT/'autonomy/evidence/unattended_20261026/RELEASE_MANIFEST.json'
    manifest=load(manifest_path)
    manifest.update(u1_original_owner_session_latest=record,current_engineering_source_commit=SOURCE,
        installable_release=False,development_complete=False,release_ready=False,
        production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,
        allow_cancel_dispatch=False,smtp_enabled=False)
    save(manifest_path,manifest)
    print(json.dumps(dict(source_commit=SOURCE,tests=tests['tests_run'],review=review['status'],all_green=comparison['all_green'])))


if __name__=='__main__':main()
