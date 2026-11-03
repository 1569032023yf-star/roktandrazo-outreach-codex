"""离线交付记录 / Offline delivery records. No production operations."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = 'd47e5d9f2f51bf0acc2f9dc4d3dc2a12b6287923'
BASE = '061549f0a146606eec1a62f2634e56ecd99d5ea1'
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def main():
    tests = load(HERE/'fixed-validation/TARGETED.json')
    review = load(HERE/'INDEPENDENT_RESULT.json')
    comparison = load(HERE/'fixed-comparison/COMPARISON.json')
    package = load(HERE/'package/BUILD.json')
    channel = load(HERE/'CHANNEL_PACKAGE.json')
    assert tests['source_commit'] == review['source_commit'] == package['source_commit'] == channel['source_commit'] == comparison['candidate_commit'] == SOURCE
    assert tests['passed'] and review['status'] == 'OFFLINE_SCOPED_REVIEW_PASSED' and comparison['complete']
    files = []
    for name in subprocess.check_output(['git','diff','--name-only',BASE,SOURCE], cwd=ROOT, text=True).splitlines():
        raw = (ROOT/name).read_bytes()
        blob = subprocess.check_output(['git','show',SOURCE+':'+name], cwd=ROOT)
        assert raw.replace(b'\r\n',b'\n') == blob.replace(b'\r\n',b'\n')
        files.append(dict(path=name,actual_sha256=hashlib.sha256(raw).hexdigest(),git_blob_sha256=hashlib.sha256(blob).hexdigest(),normalized_match=True))
    save(HERE/'SOURCE_MANIFEST.json',dict(source_commit=SOURCE,baseline_commit=BASE,files=files))
    artifacts = []
    for folder in ('package','channel-package'):
        for p in sorted((HERE/folder).rglob('*')):
            if p.is_file(): artifacts.append(dict(path=p.relative_to(HERE).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    p = HERE/'publisher-support.zip'
    artifacts.append(dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    save(HERE/'ARTIFACT_MANIFEST.json',dict(source_commit=SOURCE,files=artifacts))
    now = datetime.now(timezone.utc).isoformat()
    next_zh = '完成正式backend与原Inventory所有者/服务事件消费者的接线及合同核验；整合完整发布版后，在明确授权的隔离Windows环境验证真实首装、升级、中断恢复和回滚。'
    next_en = 'Complete formal-backend wiring to the original Inventory owner and service event consumer, including contract verification. Integrate the complete release, then validate real installation, upgrade, interruption recovery and rollback in an explicitly authorized isolated Windows environment.'
    record = dict(source_commit=SOURCE,updated_at=now,report=HERE.relative_to(ROOT).as_posix()+'/REPORT.md',tests=tests,independent_review=review['status'],independent_tests=review['independent_tests'],current_full_regression=comparison,current_package=package,publisher_package=channel,authenticated_sealed_admission_connected=True,connected_install_maintenance_offline_review_passed=True,formal_backend_integrated=False,formal_maintenance_integrated=False,installable_release=False,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,inventory_id='1784775229336',next_action=next_en,next_action_zh=next_zh)
    save(HERE/'RESULT.json',record)
    for rel in ('autonomy/AUTONOMOUS_TASK_QUEUE.json','autonomy/runtime/queue.json'):
        p=ROOT/rel; value=load(p)
        task=next(t for t in value['tasks'] if t['id']=='A-unattended-architecture-20261026')
        task.update(candidate_commit=SOURCE,updated_at=now,status='in_progress',checkpoint=record['report'],targeted_tests=tests['tests_run'],review_status=review['status'],full_regression=comparison,u1_publisher_admission_latest=record,next_action=next_en,next_action_en=next_en,next_action_zh=next_zh,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False)
        value.update(u1_publisher_admission_latest=record,checkpoint=record['report'],updated_at=now)
        save(p,value)
    text=f'''# U1 原发布器接线交付 / Original Publisher admission delivery

固定源码 / Fixed source: `{SOURCE}`

## 实际工程 / Implemented engineering

原Publisher的Bearer认证、配置一致性seal与新增安装入口已在离线源码接通。批准仅来自受保护的原配置，HTTP不得提供任意命令、路径、摘要或授权。安装维护权取得、持续验证、进程证据、终态核验、释放与显式补偿接入同一调用路径；重复调用仅返回日志，不重复执行。seal是配置一致性校验，依赖受信本地所有权，并非密码签名或安装授权。
The original Publisher Bearer authentication, configuration-consistency seal and new installation admission are connected in offline source. Approval comes only from protected original configuration; HTTP cannot supply arbitrary commands, paths, hashes or grants. Maintenance acquisition, continuous verification, process evidence, terminal verification, release and explicit compensation share the connected path. Duplicate calls return journal evidence without re-execution. The seal checks configuration consistency and depends on trusted local ownership; it is neither a cryptographic signature nor an installation grant.

独审发现补偿子会话HELD时退出会被永久阻断。现以绑定完整会话日志、零进程意图的NO_PROCESS_INTENT证据修复；事务内再次核验证据以防竞争。仅根HELD可显式NOT_STARTED释放；补偿子会话必须以新恢复编号继续补偿，不能直接释放原维护权。INSTALL_INTENT无进程记录、LAUNCH-only等未知状态仍STOP_AND_PRESERVE。
Independent review found a blocked recovery when a compensation child exited at HELD. A NO_PROCESS_INTENT proof now binds the complete session journal and absence of process intent, with revalidation inside the transaction. Only a root HELD session may explicitly release as NOT_STARTED. A compensation child requires another recovery ID and cannot abandon the original authority. INSTALL_INTENT without process evidence and LAUNCH-only remain STOP_AND_PRESERVE.

## 测试与审核 / Tests and review

固定候选组合 **{tests['tests_run']}/{tests['tests_run']}通过**；独审 **94/94通过**，另六项探针通过。结论OFFLINE_SCOPED_REVIEW_PASSED，范围为已连接安装维护代码路径。HTTP成功路径使用安装/观察回调替身，协调器测试不能拼接成一次真实全安装验收。旧595候选的阻断诊断保留，不能继承其结果。
Fixed-candidate combined validation: **{tests['tests_run']}/{tests['tests_run']} passed**. Independent validation: **94/94 passed**, plus six probes. OFFLINE_SCOPED_REVIEW_PASSED covers the connected installation-maintenance code path. HTTP success tests use installer/observer callback doubles; coordinator tests cannot be combined into a claim of one real end-to-end installation. The blocked 595 diagnostic is retained and its results are not inherited.

可比全量回归：基线`{comparison['baseline_commit']}`及候选各833项，各37 failures、17 errors，失败和错误ID一致。NO_NEW_REGRESSION=true；ALL_GREEN=false。没有宣称全部通过。
Comparable full regression: baseline `{comparison['baseline_commit']}` and candidate each ran 833 tests with 37 failures and 17 errors. Failure/error IDs match. NO_NEW_REGRESSION=true; ALL_GREEN=false. This is not an all-pass result.

## 工程包及摘要 / Engineering artifacts and hashes

真实AMD64工程包含71个载荷文件；原Publisher配套包含17个精确文件并通过实际解压后的新进程导入核验。原bin文件绑定旧SHA，新helper要求ABSENT；不扩大宿主文件白名单。两个包均不是完整可安装发布版，不含生产配置、凭据或通道自动更新器。外部CPython未捆绑。全部文件摘要见ARTIFACT_MANIFEST.json。
The actual AMD64 engineering package contains 71 payload files. The Publisher support archive contains 17 exact files and passed fresh-process import verification after extraction. Original bin members bind prior hashes; new helpers require ABSENT. The host allowlist is not expanded. Neither archive is a complete installable release; production configuration, credentials and a channel self-updater are absent. External CPython is not bundled. All file hashes are in ARTIFACT_MANIFEST.json.

- install.zip SHA256: `{package['artifacts']['install.zip']}`
- rollback-tools.zip SHA256: `{package['artifacts']['rollback-tools.zip']}`
- Host manifest SHA256: `{package['manifest_sha256']}`
- publisher-support.zip SHA256: `{channel['artifact_sha256']}`
- Publisher manifest SHA256: `{channel['manifest_sha256']}`

## 剩余工程与验收 / Remaining engineering and acceptance

{next_zh}
{next_en}

正式backend当前仍为离线合同；原Inventory所有者至正式服务事件消费者的实际执行链尚未完成。原Inventory和原Publisher准入补丁必须在同一受控窗口交付并刷新受信配置/seal，当前未执行。实际PowerShell入口、SCM/ACL成功路径、无人值守生命周期尚未验证。WorkBuddy下一步仅针对最终完整候选和新增行为核验，不重复索要已消费P1证据；当前不启动现场验收或生产安装。
The backend remains an offline contract; the actual execution chain from the original Inventory owner to the formal service event consumer is incomplete. Original Inventory and Publisher admission patches require the same controlled rollout window and trusted configuration/seal refresh; none was applied. Real PowerShell entry, successful SCM/ACL paths and unattended lifecycle remain unverified. WorkBuddy should verify the final complete candidate and new behavior without repeating consumed P1 evidence. Site acceptance and production installation are not started now.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

接受既定非对称ACL裁决。本轮仅离线开发和隔离测试，未修改现场发布器、生产数据库/账本/ACL/目录/服务/Inventory或系统配置。
The accepted asymmetric ACL ruling is retained. This work used offline development and isolated tests only, without changing the site Publisher, production database/ledger/ACL/directories/services/Inventory or system configuration.
'''
    (HERE/'REPORT.md').write_text(text,encoding='utf-8')
    preface=f'''# U1 原发布器接线 / Original Publisher admission

固定源码 / Fixed source: `{SOURCE}` | {now}

234项组合、94项独审和六项探针通过；833项全量回归双方37失败/17错误，非全绿。工程包已重建，完整安装交付未完成。
234 combined tests, 94 independent tests and six probes passed. Both 833-test full runs have 37 failures/17 errors; not all green. Engineering archives rebuilt; complete installable delivery remains incomplete.

{next_zh}
{next_en}

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false`

[双语报告 / Bilingual report](../u1_publisher_admission_20261103/REPORT.md)

---

'''
    base=ROOT/'autonomy/evidence/unattended_20261026'
    for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
        p=base/name; old=p.read_text(encoding='utf-8')
        if SOURCE not in old.split('---',1)[0]: p.write_text(preface+old,encoding='utf-8')
    p=base/'RELEASE_MANIFEST.json'; value=load(p)
    value.update(current_engineering_checkpoint=record,latest_engineering_commit=SOURCE,current_release_ready=False)
    save(p,value)

if __name__ == '__main__': main()
