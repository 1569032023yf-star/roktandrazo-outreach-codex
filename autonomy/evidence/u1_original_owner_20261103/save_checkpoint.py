"""原所有者排他证据 / Original-owner exclusion evidence. Offline only."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
SOURCE='4b0353cbc4a5c69998fdd597d2bb884f7f5da8d0'
BASE='cc6434e1fdff68c0069a5cd9a85fe22c4b9d994d'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    tests=load(HERE/'fixed-validation/TARGETED.json');review=load(HERE/'INDEPENDENT_RESULT.json')
    comparison=load(HERE/'fixed-comparison/COMPARISON.json');package=load(HERE/'fixed-package/BUILD.json');channel=load(HERE/'CHANNEL_PACKAGE.json')
    assert tests['source_commit']==review['source_commit']==comparison['candidate_commit']==package['source_commit']==channel['source_commit']==SOURCE
    assert tests['passed'] and comparison['complete'] and review['status']=='OFFLINE_SCOPED_REVIEW_PASSED'
    artifact_review=load(HERE/'INDEPENDENT_PACKAGE_RESULT.json')
    assert artifact_review['source_commit']==SOURCE
    assert artifact_review['engineering_artifacts']==package['artifacts']
    assert artifact_review['support_sha256']==channel['artifact_sha256']
    package=dict(package,independent_review=review['status'],review_evidence='INDEPENDENT_PACKAGE_RESULT.json')
    files=[]
    for name in subprocess.check_output(['git','diff','--name-only',BASE,SOURCE],cwd=ROOT,text=True).splitlines():
        raw=(ROOT/name).read_bytes();blob=subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT)
        assert raw.replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n')
        files.append(dict(path=name,actual_sha256=hashlib.sha256(raw).hexdigest(),git_blob_sha256=hashlib.sha256(blob).hexdigest(),normalized_match=True))
    save(HERE/'SOURCE_MANIFEST.json',dict(source_commit=SOURCE,baseline_commit=BASE,files=files))
    artifacts=[]
    for folder in ('fixed-package','fixed-channel-package'):
        for p in sorted((HERE/folder).rglob('*')):
            if p.is_file():artifacts.append(dict(path=p.relative_to(HERE).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    p=HERE/'fixed-publisher-support.zip';artifacts.append(dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    save(HERE/'ARTIFACT_MANIFEST.json',dict(source_commit=SOURCE,files=artifacts))
    now=datetime.now(timezone.utc).isoformat()
    next_zh='继续正式backend与原Inventory所有者及服务事件消费者接线，复用原数据库锁并加入持久事件/预算/取消/结算合同；禁止用离线supervisor锁冒充原生产所有者。完成后重建完整发布版并做授权隔离Windows生命周期验收。'
    next_en='Continue formal-backend wiring to the original Inventory owner and service event consumer, reusing the original database lock with durable event, budget, cancellation and settlement contracts. An offline supervisor lease is not the original production owner. Then rebuild the complete release and perform authorized isolated Windows lifecycle acceptance.'
    record=dict(source_commit=SOURCE,updated_at=now,report=HERE.relative_to(ROOT).as_posix()+'/REPORT.md',tests=tests,independent_review=review,current_full_regression=comparison,current_package=package,publisher_package=channel,original_owner_cross_date_exclusion=True,unknown_exception_preserves_original_lock=True,shared_inventory_publisher_installer_exclusion=True,formal_backend_integrated=False,formal_maintenance_integrated=False,installable_release=False,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,inventory_id='1784775229336',next_action=next_en,next_action_zh=next_zh)
    save(HERE/'RESULT.json',record)
    for rel in ('autonomy/AUTONOMOUS_TASK_QUEUE.json','autonomy/runtime/queue.json'):
        p=ROOT/rel;value=load(p);task=next(t for t in value['tasks'] if t['id']=='A-unattended-architecture-20261026')
        task.update(candidate_commit=SOURCE,status='in_progress',updated_at=now,checkpoint=record['report'],targeted_tests=tests['tests_run'],review_status=review['status'],full_regression=comparison,u1_original_owner_latest=record,next_action=next_en,next_action_en=next_en,next_action_zh=next_zh)
        value.update(u1_original_owner_latest=record,checkpoint=record['report'],updated_at=now);save(p,value)
    text=f'''# 原Inventory所有者排他修复 / Original Inventory owner exclusion repair

固定源码 / Fixed source: `{SOURCE}`

原正式调用链为bd_orchestrator.stage_inventory → bd_db.acquire_run_lock；此前按日期及超时接管，跨日可能并行，异常finally还会释放未知副作用的锁。现同BEGIN IMMEDIATE检查全部Inventory日期，仅明确released可继续；空值、NULL、异常持有者均保留。SystemExit及业务异常均保留原锁，正常已知返回保留原释放合同。未知不会因时间、进程重启或相同holder而重放。
The actual owner call path is bd_orchestrator.stage_inventory → bd_db.acquire_run_lock. Previously date-scoped locks and timeout takeover could overlap across dates, while exception cleanup released locks despite unknown effects. The same BEGIN IMMEDIATE now checks every Inventory date, allowing only explicitly released rows. Empty, NULL and malformed holders remain blocked. SystemExit and business exceptions preserve the original lock; known normal returns retain the existing release contract. Time, process restart and repeated holders do not authorize unknown replay.

共享inventory_lock_blocked同时接入原owner、原Publisher及安装维护准入。初版68ec独审发现空值在安装准入仍被放行，现已修复并重新固定审核。未修改非Inventory锁的既有过期合同；未创建新锁系统、调度器或生产运行。
The shared inventory_lock_blocked predicate is connected to the original owner, original Publisher and installer maintenance admission. Independent review of initial 68ec found empty values still admitted installation maintenance; this was repaired before the current fixed review. Non-Inventory expiry behavior is unchanged. No replacement lock system, scheduler or production run was created.

## 验证 / Verification

当前候选组合{tests['tests_run']}项，passed={tests['passed']}；独审详见INDEPENDENT_REVIEW.md及INDEPENDENT_RESULT.json，结论{review['status']}。原SQLite及真实子进程退出/并发验证仅针对临时数据库；实际stage函数以AST隔离加载，业务Provider回调为替身，不证明真实业务采集。
Current fixed-candidate combined validation: {tests['tests_run']} tests, passed={tests['passed']}. See INDEPENDENT_REVIEW.md and INDEPENDENT_RESULT.json for independent evidence, status {review['status']}. Original SQLite logic and actual child-process exit/concurrency probes use temporary databases only. The actual stage function is AST-loaded in isolation with Provider callback doubles; this does not prove business collection.

可比全量：基线`{comparison['baseline_commit']}`与当前候选各{comparison['candidate_run']}项；基线{comparison['baseline_failures']} failures/{comparison['baseline_errors']} errors，候选{comparison['candidate_failures']} failures/{comparison['candidate_errors']} errors。NO_NEW_REGRESSION={comparison['no_new_regression']}；ALL_GREEN={comparison['all_green']}。不继承旧候选结果。9cbc初次全量60失败/17错误，新增23项为当前异常释放旧预期及历史补丁读取演进源码；保留原诊断。当前入口保留未知锁，历史补丁改用原固定SHA字节夹具，未放宽产品门禁。
Comparable full regression: baseline `{comparison['baseline_commit']}` and current candidate each ran {comparison['candidate_run']} tests. Baseline has {comparison['baseline_failures']} failures/{comparison['baseline_errors']} errors; candidate has {comparison['candidate_failures']} failures/{comparison['candidate_errors']} errors. NO_NEW_REGRESSION={comparison['no_new_regression']}; ALL_GREEN={comparison['all_green']}. Old-candidate results are not inherited. Initial 9cbc had 60 failures/17 errors: 23 added failures reflected outdated exception-release expectations and historical patch tests reading evolving source. That diagnostic is retained. Current unknown work remains fenced; historical tests use the original fixed-hash byte fixture without relaxing product gates.

## 制品 / Artifacts

真实AMD64宿主重新构建，71文件；Publisher支持包17文件，实际解压后新进程导入通过。新原owner companion精确绑定bd_db.py与bd_orchestrator.py，含两文件前后Git blob SHA；不扩大宿主白名单、不自动部署。安装包仍为工程包，正式backend未闭环，不能作为完整可安装发布版。全部文件摘要见ARTIFACT_MANIFEST.json。
The actual AMD64 host was rebuilt with 71 files. The 17-file Publisher support archive passed a fresh-process import after extraction. The updated original-owner companion binds bd_db.py and bd_orchestrator.py with before/after Git-blob hashes, without expanding the host allowlist or deploying automatically. Artifacts remain engineering archives: the formal backend is incomplete, so they are not a complete installable release. Every artifact hash is recorded in ARTIFACT_MANIFEST.json.

- install.zip SHA256: `{package['artifacts']['install.zip']}`
- rollback-tools.zip SHA256: `{package['artifacts']['rollback-tools.zip']}`
- Host manifest SHA256: `{package['manifest_sha256']}`
- Publisher support SHA256: `{channel['artifact_sha256']}`
- Publisher manifest SHA256: `{channel['manifest_sha256']}`

## 未完成及下一步 / Remaining work and next steps

{next_zh}
{next_en}

WorkBuddy仅在完整候选、独审及明确授权后，对最终SHA验证真实PowerShell入口、Disabled/Stopped服务、非对称ACL、首装/升级/中断恢复/回滚及唯一Inventory排他。已提交P1证据不重复索要。当前不执行现场动作，生产数据库/账本/目录/ACL/服务/Inventory及现场发布器均未修改。
After a complete candidate, independent review and explicit authorization, WorkBuddy should verify the final SHA against the actual PowerShell entry, Disabled/Stopped service, asymmetric ACLs, first install/upgrade/interruption recovery/rollback and sole-Inventory exclusion. Previously submitted P1 evidence is not requested again. No site action was performed; production databases, ledgers, directories, ACLs, services, Inventory and Publisher remain unchanged.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`
'''
    (HERE/'REPORT.md').write_text(text,encoding='utf-8')
    preface=f'''# U1 原所有者排他 / Original-owner exclusion

固定源码 / Fixed source: `{SOURCE}` | {now}

原Inventory跨日期及未知退出锁保留已修复，并与Publisher/安装维护统一。组合{tests['tests_run']}项，独审{review['status']}；完整正式backend与真实Windows验收未完成。
Original Inventory cross-date and unknown-exit lock preservation is repaired and shared with Publisher/installer maintenance. Combined tests: {tests['tests_run']}; review: {review['status']}. The complete formal backend and real Windows acceptance remain incomplete.

{next_zh}
{next_en}

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false`

[双语报告 / Bilingual report](../u1_original_owner_20261103/REPORT.md)

---

'''
    base=ROOT/'autonomy/evidence/unattended_20261026'
    for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
        p=base/name;old=p.read_text(encoding='utf-8')
        if SOURCE not in old.split('---',1)[0]:p.write_text(preface+old,encoding='utf-8')
    p=base/'RELEASE_MANIFEST.json';value=load(p);value.update(current_engineering_checkpoint=record,latest_engineering_commit=SOURCE,current_release_ready=False);save(p,value)
if __name__=='__main__':main()
