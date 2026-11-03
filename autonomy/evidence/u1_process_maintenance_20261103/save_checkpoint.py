"""Persist offline evidence / 保存离线证据，不操作任何生产资源。"""
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = '8dde11230772484cc86ee7dfc3d2d45f891ec58a'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    tests = load(HERE/'validation/TARGETED.json')
    review = load(HERE/'INDEPENDENT_RESULT.json')
    assert tests['source_commit'] == review['source_commit'] == SOURCE
    assert tests['passed'] and not tests['failures'] and not tests['errors'] and not tests['skips']
    assert review['status'] == 'OFFLINE_SCOPED_REVIEW_PASSED'
    files = []
    for entry in review['file_hashes']:
        path = entry['path']
        actual = (ROOT/path).read_bytes()
        blob = subprocess.check_output(['git', 'show', SOURCE+':'+path], cwd=ROOT)
        assert actual.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n')
        files.append(dict(path=path, actual_sha256=hashlib.sha256(actual).hexdigest(),
                          git_blob_sha256=hashlib.sha256(blob).hexdigest(),
                          matches_fixed_source_after_newline_normalization=True))
    save(HERE/'SOURCE_MANIFEST.json', dict(source_commit=SOURCE, files=files))
    now = datetime.now(timezone.utc).isoformat()
    next_zh = '完成受控安装进程的逐步维护权跨进程核验、固定身份及独立文件/日志/SCM/ACL最终核验；完整调用链独审后再制作可安装版本，保持生产门禁关闭。'
    next_en = 'Complete per-step cross-process maintenance checks, pinned process identity and independent file/journal/SCM/ACL final verification; review the complete chain before producing the installable release. Keep production gates closed.'
    record = dict(updated_at=now, source_commit=SOURCE,
                  description_zh='原安装维护会话接入真实进程树的主线程维护权监管；完整进程适配仍未完成。',
                  description_en='Live parent-thread authority supervision connects the install session to real process trees; complete process adaptation remains unfinished.',
                  report=str(HERE.relative_to(ROOT)).replace('\\','/')+'/REPORT.md',
                  tests=tests, independent_review=review['status'], independent_tests=27,
                  independent_additional_probes=2, complete_call_chain_review_passed=False,
                  parent_process_watchdog_implemented=True, process_adapter_complete=False,
                  independent_final_verifier_complete=False, formal_maintenance_integrated=False,
                  development_complete=False, release_ready=False, production_deployed=False,
                  production_accepted=False, allow_install=False, allow_dispatch=False,
                  allow_cancel_dispatch=False, smtp_enabled=False, inventory_id='1784775229336',
                  current_full_regression='NOT_RUN_FOR_THIS_SOURCE',
                  current_package='NOT_BUILT_INCOMPLETE_INTEGRATION', next_action=next_en, next_action_zh=next_zh)
    save(HERE/'RESULT.json', record)
    for rel in ('autonomy/AUTONOMOUS_TASK_QUEUE.json', 'autonomy/runtime/queue.json'):
        path = ROOT/rel
        value = load(path)
        task = next(t for t in value['tasks'] if t['id']=='A-unattended-architecture-20261026')
        task.update(candidate_commit=SOURCE, updated_at=now, status='in_progress',
                    review_status=review['status'], targeted_tests=tests['tests_run'],
                    full_regression='NOT_RUN_FOR_THIS_SOURCE', next_action=next_en,
                    next_action_en=next_en, next_action_zh=next_zh,
                    checkpoint=record['report'], u1_process_maintenance_latest=record,
                    allow_install=False, allow_dispatch=False, allow_cancel_dispatch=False,
                    smtp_enabled=False, development_complete=False, release_ready=False,
                    production_deployed=False, production_accepted=False)
        save(path, value)
    report = f'''# U1 安装进程维护监管 / Installer process maintenance supervision

固定源码 / Fixed source: `{SOURCE}` | {now}

本轮实际完成：现有进程树监管器接入主线程维护权检查。启动前、Windows挂起进程恢复前、运行期间及已核验清理后均要求严格True；失权或检查异常沿用真实Windows Job整树终止与清理核验，不释放维护标记。维护会话监管绑定原Inventory/source/manifest/target/action及INSTALL_INTENT阶段。没有新增调度器或外部安装授权开关。
Implemented: The existing process-tree supervisor now checks maintenance on its calling thread before launch, before Windows resume, while running and after verified cleanup. Only strict True permits continuation. Loss/errors invoke existing whole-Job termination and cleanup verification without releasing maintenance. Session supervision binds the original Inventory/source/manifest/target/action and INSTALL_INTENT phase. No scheduler or external installation grant was added.

## 测试与审核 / Tests and review

- 本固定源码组合测试：**{tests['tests_run']} PASS / {tests['seconds']}s**，失败、错误及跳过均0；包含ACL、安装、发布恢复、backend及真实Windows进程树测试。证据：validation/TARGETED.json和逐项输出。
  Combined fixed-source tests: **{tests['tests_run']} PASS / {tests['seconds']}s**, zero failures/errors/skips, including ACL, installation, publisher recovery, backend and real Windows process trees. See validation/TARGETED.json and full output.
- 独立审核：**27项通过，另2项隔离探针通过**，无新增可确认阻断，仅为OFFLINE_SCOPED_REVIEW_PASSED。真实验证恢复执行前拒绝无子进程副作用、清理后失权不能返回成功。未声称完整链路独审通过。
  Independent review: **27 tests plus two isolated probes passed**, no new confirmed blockers, scoped approval only. Probes verify pre-resume rejection prevents child effects and post-cleanup authority loss cannot return success. Complete-chain approval is not claimed.
- 失权测试真实终止父子进程并核验PID消失。安装会话集成测试以UNKNOWN阶段模拟会话失效，不冒称实际handoff；既有handoff/进程退出/回滚中断测试独立保留。
  Lost-authority tests terminate real parents/descendants and verify PID disappearance. The session integration fixture invalidates its phase to UNKNOWN; it does not impersonate a real handoff. Existing handoff/death/interrupted-rollback tests remain separate.

## 未完成与下一步 / Remaining work and next step

{next_zh}
{next_en}

父进程周期监管不替代每次子进程mutation的同步权限桥；当前仍不是完整可安装交付。正式入口身份/seal接线、旧进程身份与终止核验、独立最终核验器、完整调用链审核和WorkBuddy现场无人值守验收未完成。本源码没有新安装包或833项全量回归，不继承旧包哈希和旧候选成绩；历史37 failures/17 errors不是全绿。
Parent polling does not replace synchronous authority checks for each child mutation; this is not a complete installable delivery. Supported-entry identity/seal wiring, previous-process identity/termination verification, the independent final verifier, full-chain review and WorkBuddy unattended acceptance remain incomplete. No new package or 833-test regression is assigned to this source; old artifact hashes/results are not inherited. Historical 37 failures/17 errors are not all green.

WorkBuddy下一步：待完整候选与审核完成后，按固定SHA验证Windows无人值守安装、升级、退出恢复及回滚；当前无需重复提交已消费的P1环境资料，也不启动生产验证。
WorkBuddy next: after the complete candidate and review, verify unattended Windows installation, upgrade, interrupted recovery and rollback against the fixed SHA. Do not resubmit consumed P1 environment evidence or begin production validation now.

## 门禁、未执行与敏感信息 / Gates, non-execution and sensitive information

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

未操作生产数据库、账本、ACL、服务、代理、注册表、系统任务或生产Inventory；未修改现场Publisher、未提取凭据。所有本轮进程副作用仅限隔离临时文件；源码和报告不含真实凭据或客户数据。风险为尚未闭合的跨进程授权及最终核验，不以范围测试替代真实安装验收。
No production database/ledger/ACL/service/proxy/registry/task/Inventory operation, site publisher modification or credential extraction occurred. Process effects were confined to isolated temporary files; source/reports contain no real credentials or customer data. Cross-process authorization and final verification remain open risks; scoped tests do not replace installation acceptance.
'''
    (HERE/'REPORT.md').write_text(report, encoding='utf-8')
    preface = f'''# U1 安装进程维护监管 / Install process maintenance supervision

固定源码 / Fixed source: `{SOURCE}` | {now}

真实进程树维护权监管已接入；组合{tests['tests_run']} PASS，独审27项及2探针通过，范围独审结论。完整跨进程权限桥和独立最终核验尚未完成，不进入真实安装或无人值守验收。
Real process trees now support live maintenance supervision; {tests['tests_run']} combined tests and 27 independent tests plus two probes passed. This is scoped approval. The complete cross-process authority bridge and independent final verification remain unfinished; do not begin installation/unattended acceptance.

下一步 / Next: {next_zh}

{next_en}

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false`

[双语报告 / Bilingual report](../u1_process_maintenance_20261103/REPORT.md)

---

'''
    for filename in ('U1_CURRENT_CHECKPOINT.md', 'U1_DELIVERY_STATUS.md'):
        path = ROOT/'autonomy/evidence/unattended_20261026'/filename
        path.write_text(preface+path.read_text(encoding='utf-8'), encoding='utf-8')
    path = ROOT/'autonomy/evidence/unattended_20261026/RELEASE_MANIFEST.json'
    value = load(path)
    value.update(current_engineering_checkpoint=record, latest_engineering_commit=SOURCE,
                 current_release_ready=False)
    save(path, value)


if __name__ == '__main__':
    main()
