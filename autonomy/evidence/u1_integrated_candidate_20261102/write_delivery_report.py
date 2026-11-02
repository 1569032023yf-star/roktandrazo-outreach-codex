"""Assemble actual pinned evidence / 汇总真实固定候选证据。"""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
FINAL=OUT/'final'
SHA='70ee72177a40408d5b03a415b3eef3fb51059589'


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    t=read(FINAL/'TARGETED.json');c=read(FINAL/'COMPARISON.json');p=read(FINAL/'PACKAGE_VALIDATION.json')
    pt=read(FINAL/'PACKAGED_TEST.json');review=read(OUT/'INDEPENDENT_RESULT.json')
    assert all(x['source_commit']==SHA for x in (t,p,pt,review))
    assert c['candidate_commit']==SHA and c['complete'] and t['passed'] and pt['passed']
    assert review['status']=='OFFLINE_REVIEW_PASSED'
    counts=Counter()
    for line in (FINAL/'TARGETED_OUTPUT.txt').read_text(encoding='utf-8').splitlines():
        match=re.match(r'^\S+ \(([^)]+)\) \.\.\. ok$',line)
        if match:counts[match[1].split('.')[0]]+=1
    assert sum(counts.values())==t['tests_run'],counts
    now=datetime.now(timezone.utc).isoformat()
    package=p['artifacts'];report_path='autonomy/evidence/u1_integrated_candidate_20261102/REPORT.md'
    states=dict(DEVELOPMENT_COMPLETE=False,RELEASE_READY=False,PRODUCTION_DEPLOYED=False,PRODUCTION_ACCEPTED=False)
    current=dict(description_zh='安装文件与恢复、现有所有者事件通道的固定离线集成候选；正式执行集成未完成。',
        description_en='Pinned offline integration of owned-file recovery and existing-owner event transport; formal execution integration remains incomplete.',
        source_commit=SHA,updated_at=now,report=report_path,independent_review=review['status'],
        tests=t,regression=c,package_validation='final/PACKAGE_VALIDATION.json',artifacts=package,
        manifest_sha256=p['manifest_sha256'],host_manifest_sha256=p['host_manifest_sha256'],
        states=states,offline_file_lifecycle_verified=True,offline_event_chain_verified=True,
        formal_backend_integrated=False,formal_maintenance_lease_enforced=False,production_owner_configuration_changed=False,
        allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,inventory_id='1784775229336')
    write(OUT/'DELIVERY_RESULT.json',current)
    table='\n'.join('| `'+m+'` | '+str(counts[m])+' | PASS |' for m in t['modules'])
    text=f'''# U1 固定集成候选交付报告 / Pinned integrated candidate delivery report

时间 / Time: {now}
固定源码 / Fixed source: `{SHA}`
可比基线 / Comparable baseline: `{c['baseline_commit']}`

**当前仍未达到完整交付目标。** 本轮完成可恢复文件安装/升级/回滚及现有所有者到服务邮箱的离线执行链集成，形成实际 AMD64 包并通过独审。正式 backend 适配、安装维护租约强制验证及原生产所有者的接入配置尚未完成。它们不是等待重复环境证据，而是后续工程和受控集成工作。

**The complete delivery objective is still unmet.** This run integrates recoverable file installation/upgrades/rollback and the offline existing-owner/service-mailbox execution chain, builds an actual AMD64 package and passes independent review. Formal backend adaptation, enforced installation maintenance-lease validation and production-owner connection configuration remain. These are engineering/controlled-integration tasks, not requests for repeated environment evidence.

## 已完成 / Implemented

1. 继续接受裁决 `6520202418`；不推翻 Code Root 继承加服务 RX、State Root 保护 DACL 的既有实现。ACL 源码 `0db17b5`、审核 `91aa60c` 和发布恢复 `82031ac` 已合入当前祖先链；本轮重新执行相关测试，不直接继承旧成绩。
   Continue accepting the asymmetric ACL ruling. Existing ACL and publication-recovery work is in the candidate ancestry and its tests were rerun; historical results are not substituted.
2. `host_file_transaction.py` 从独立批准哈希绑定的 v2 旧凭据推导精确文件所有权；支持新建、替换、删除、旧字节备份、ABSENT 恢复；拒绝未受管覆盖、路径/大小写/祖先/暂存冲突及硬链接。持久意图先于效果，效果后逐字节哈希回读；残缺日志和未知结果停止保留，不能继续正向重放。
   Exact v2-receipt ownership supports new/replaced/deleted files, old-byte backups and ABSENT restoration. It rejects unmanaged overwrites, path/case/ancestor/staging collisions and hardlinks. Durable intents precede effects and hash readback follows them; torn or unknown state stops without forward replay.
3. 安装入口委托持久协调器。首次安装与升级均保持服务 Disabled/Stopped；失败尝试已知补偿，未知结果保留；显式 RecoverInstall/Rollback 可在进程或回滚中断后恢复。旧事务回滚先检查全部文件，不能删除更新候选的服务。首次回滚按记录身份清理事务新建空 Code/State 根；升级保留原状态，仅清理本事务空目录。相同包可在已确认回滚后用新显式 OperationId 再首装，未知操作不能换 ID 绕过封锁。
   The durable coordinator keeps service registration Disabled/Stopped through first install/upgrades. Failures attempt known compensation and preserve unknown results; explicit recovery handles process/rollback interruption. Historical rollback cannot remove a newer service. Fresh rollback removes only identity-recorded empty roots; upgrades preserve existing state and remove only their own empty directories. A new explicit operation ID permits reinstall after confirmed rollback, never bypassing unknown-operation fences.
4. 宿主和引导配置支持 `event_runtime`。服务经认证的回环 HTTP 保存并一次性保留事件，原所有者仍持有原 supervisor 锁并核验签名、预算、取消保留和结算合同，使用原 SingleSlotAdapter/ProcessBackend。RESERVED、丢回执、凭据中途到期或 UNKNOWN 不重派；OWNER_REPORTED 仍不证明执行成功。没有新增调度器或生产触发。
   Host/bootstrap configuration supports an event runtime. Authenticated loopback HTTP persists/reserves events; the existing owner retains its lease and signed admission/budget/cancellation-reservation/settlement contracts through the existing adapter/backend. Reserved/unknown/lost-response/expired-credential cases never redispatch; owner-reported transport state is not terminal success. No scheduler or production trigger was added.
5. 安装包和回滚工具都带当前宿主/事务辅助程序。真实 PE machine=`{p['pe_machine']}`；全部 {len(p['all_files_verified'])} 个交付文件及两 ZIP 精确清单/字节校验通过。工作树与 Git 原始换行哈希分开记录，规范化后与固定源码一致。
   Both archives contain current host/transaction helpers. Actual AMD64 PE and all {len(p['all_files_verified'])} delivery files/ZIP bytes are verified. Worktree/Git raw hashes distinguish line endings and normalize to the fixed source.

## 测试与独审 / Tests and independent review

当前源码组合：**{t['tests_run']} PASS / {t['seconds']}s**，失败、错误、跳过均为 0。逐用例证据见 `final/TARGETED_OUTPUT.txt`。
Current pinned combined run: **{t['tests_run']} PASS / {t['seconds']}s**, zero failures/errors/skips. Per-test evidence is retained.

| 模块 / Module | 数量 / Count | 结果 / Result |
| --- | ---: | --- |
{table}

覆盖首次安装、升级、旧文件删除/备份、ABSENT、重复调用、第二阶段失败补偿、历史回滚拒绝、真实进程退出、回滚中断、六个目录删除意图/效果退出点、早期根创建退出恢复、未知状态数据保留、凭据中途到期和事件回执丢失。协调器使用真实临时文件与 SCM/ACL 替身；ACL 专项使用真实临时 DACL，不能把替身称为真实 SCM 安装验收。
Coverage includes first installation/upgrades/deletion/backups/ABSENT, duplicates, compensation, historical rollback rejection, process death/interrupted rollback, six directory-cleanup crash points, early-root recovery, unknown-state preservation, credential expiry and lost event reports. Coordinator tests use real temporary files with SCM/ACL doubles; ACL tests exercise real temporary DACLs. SCM doubles are not actual service-installation acceptance.

包内实际模块：14 PASS / {pt['seconds']}s，使用 `-I -B` 并核对实际导入路径。独立审核：**{review['status']}**，同一源码另行运行 138 项全通过，详见 `INDEPENDENT_REVIEW.md` 和 `INDEPENDENT_RESULT.json`。审核发现的所有权、暂存名、过早回执、历史回滚、到期响应、根清理恢复等问题已修复后复跑；离线通过不等于发布就绪。
Actual packaged imports: 14 PASS / {pt['seconds']}s, with isolated interpreter/import-path verification. Independent review separately reran 138 tests on this same SHA. Findings were fixed and retested; offline review does not establish release readiness.

基线与候选本轮分别实际执行 **{c['baseline_run']} / {c['candidate_run']}** 项；失败 **{c['baseline_failures']} / {c['candidate_failures']}**，错误 **{c['baseline_errors']} / {c['candidate_errors']}**。失败 ID 一致=`{c['failure_ids_identical']}`，错误 ID 一致=`{c['error_ids_identical']}`，无新增回归=`{c['no_new_regression']}`。**全量不是全绿**，没有将旧 833 项成绩移植给新候选。中间 `995b109` 证据保留但不作为最终候选成绩。
Fresh baseline/candidate runs each executed the recorded counts with the listed failures/errors. Identical IDs/no-new-regression do **not** mean all green. Historical/intermediate results are not assigned to this candidate.

## 包与清单 / Artifacts and hashes

| 产物 / Artifact | SHA256 |
| --- | --- |
| `final/package/install.zip` | `{package['install.zip']}` |
| `final/package/rollback-tools.zip` | `{package['rollback-tools.zip']}` |
| `final/package/install/manifest.json` | `{p['manifest_sha256']}` |
| 内层宿主清单 / Host manifest | `{p['host_manifest_sha256']}` |

逐文件 SHA256 见清单和 `final/PACKAGE_VALIDATION.json`；源码字节哈希见 `final/SOURCE_MANIFEST.json`。ZIP 已实际生成并保留，不是设计占位。
Per-file and source-byte hashes are recorded. Archives are actual retained build outputs, not placeholders.

## 未完成工程与真实安装门禁 / Remaining engineering and installation gates

1. 正式 backend 协议、主体/信任源及真实执行适配仍未实现接通；当前 ProcessBackend 与事件链只接受 isolated_offline/production_execution=false，不应改名冒充正式链。
   Formal backend protocol/principal/trust-source adaptation is not connected. Current backend/event contracts remain explicitly isolated and cannot be relabeled as production integration.
2. 安装器尚缺通过正式发布入口实时校验原 Inventory 维护排斥租约的强制门禁。管理员身份、包哈希和 Global 安装 mutex 不能替代它。后续由 Codex 补齐源码并重新冻结、测试、独审；不得用本候选直接安装生产。
   Enforced live maintenance/exclusion validation through the formal publisher remains missing. Administrator identity, hashes and an installation mutex do not substitute for it. Codex must implement it and freeze/test/review a new candidate before any production installation.
3. 原生产所有者的接入配置未修改；本轮未启动或手动触发 Inventory。完成正式 backend 合同后，才可通过既有唯一所有者的支持入口配置服务事件连接，不创建第二调度器。
   Production-owner configuration remains unchanged. After formal backend integration, connect through the sole existing owner's supported entry point without another scheduler.
4. 真实 SCM 安装/升级/回滚、跨登录/无人登录持续运行及受控退出恢复仍需授权隔离 Windows 验收。本轮没有安装/启动服务；现有 P1 证据已消费，不要求重新提交相同环境资料。
   Actual SCM lifecycle, cross-login/unattended persistence and controlled recovery require authorized isolated Windows acceptance. No service was installed/started here; consumed P1 evidence is not requested again.

## WorkBuddy 下一步 / WorkBuddy next verification

- 先只读核对固定提交、两 ZIP 和逐文件 SHA；确认 v2 所有权与 operation_id 证据；可在既有隔离环境复跑本轮协调器/ACL/事件测试，保留原始日志。
  First verify fixed source/archive/file hashes and v2 ownership/operation records read-only; optionally rerun the isolated coordinator/ACL/event tests and retain raw logs.
- 待 Codex 补齐上述正式接入和租约门禁并交付新固定候选后，在授权隔离 Windows 验证真正 Disabled/Stopped 首装、升级、删除/ABSENT 回滚、进程和回滚中断恢复及无人登录持续性；未知结果不得重放。
  After Codex completes the formal adapter/lease gate and provides a newly reviewed candidate, verify actual Disabled/Stopped SCM lifecycle and unattended/crash behavior in an authorized isolated Windows environment; never replay unknown outcomes.
- 不重复收集已提交的 P1/ACL 裁决证据，不操作生产 Inventory、账本、数据库、ACL 或服务。
  Do not recollect accepted P1/ruling evidence or mutate production Inventory, ledgers, databases, ACLs or services.

## 最终状态 / Final state

`DEVELOPMENT_COMPLETE=false`
`RELEASE_READY=false`
`PRODUCTION_DEPLOYED=false`
`PRODUCTION_ACCEPTED=false`

`allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

本轮仅离线开发和隔离测试；没有生产 ACL/目录/注册表/代理/系统任务、服务或数据库/账本写入，没有新增调度器或触发生产 Inventory。既有 rokt-razo 自动化频率未改，新证据与队列将供其接续工程；本报告不将测试通过当作完整项目交付完成。
Only offline development/isolated tests were performed. No production ACL/directory/registry/proxy/task/service/database/ledger changes, second scheduler or Inventory trigger occurred. Existing automation cadence is unchanged; the updated queue/evidence supports continuation. Passing tests is not completion of the full project.
'''
    (OUT/'REPORT.md').write_text(text,encoding='utf-8')
    checkpoint=f'''# U1 固定集成候选 / Pinned integrated candidate

固定源码 / Fixed source: `{SHA}`
更新时间 / Updated: {now}

中文：真实 AMD64 包 65 文件校验通过；当前组合 138 PASS、独审 138 PASS、包内模块 14 PASS。已补首次安装/升级/精确文件与目录恢复、ABSENT、故障补偿与进程退出恢复、现有所有者到服务事件邮箱的离线链。原 ACL 裁决继续接受。全量回归基线/候选各 {c['baseline_run']} 项，均 {c['candidate_failures']} failures/{c['candidate_errors']} errors，失败/错误 ID 一致={c['failure_ids_identical'] and c['error_ids_identical']}，不是全绿。

English: Verified actual AMD64 package/65 files; 138 combined, 138 independent and 14 packaged-import tests passed. First install/upgrades/exact file-directory recovery, ABSENT, compensation/crash recovery and offline existing-owner/service-event transport are integrated. The accepted ACL ruling remains in force. Fresh full baseline/candidate runs are not all green; see recorded counts/IDs.

未完成 / Remaining: 正式 backend 适配、安装维护租约强制验证及生产原 owner 接入配置。Formal backend adaptation, enforced maintenance-lease admission and production-owner connection configuration remain. Codex continues engineering; do not request repeated WorkBuddy P1 evidence or install this candidate in production.

报告 / Report: [REPORT.md](../u1_integrated_candidate_20261102/REPORT.md)
`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`
`allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false`

---

'''
    for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
        path=ROOT/'autonomy/evidence/unattended_20261026'/name
        path.write_text(checkpoint+path.read_text(encoding='utf-8-sig'),encoding='utf-8')
    path=ROOT/'autonomy/AUTONOMOUS_TASK_QUEUE.json';q=read(path)
    task=next(x for x in q['tasks'] if x['id']=='A-unattended-architecture-20261026')
    task.update(candidate_commit=SHA,baseline_commit=c['baseline_commit'],checkpoint=report_path,status='in_progress',review_status=review['status'],targeted_tests=t['tests_run'],release_ready=False,production_deployed=False,development_complete=False,production_accepted=False,
        full_regression=f"FRESH_{c['baseline_run']}_EACH_{c['candidate_failures']}_FAILURES_{c['candidate_errors']}_ERRORS_NOT_ALL_GREEN",
        next_action='Implement enforced formal maintenance-lease admission and formal backend protocol adaptation; then connect the existing owner through its supported entry point and freeze a new candidate. No production execution.',
        next_action_zh='补齐正式维护租约强制验证和正式backend适配，再通过原所有者支持入口接入并冻结新候选；不执行生产操作。',
        u1_actual_delivery_latest=current,u1_integrated_delivery_latest=current,updated_at=now)
    task['next_action_en']=task['next_action']
    q.update(u1_integrated_delivery_latest=current,checkpoint=report_path,updated_at=now)
    write(path,q)
    path=ROOT/'autonomy/evidence/unattended_20261026/RELEASE_MANIFEST.json';manifest=read(path)
    manifest['current_candidate']=current;manifest['latest_candidate_commit']=SHA
    manifest['current_release_ready']=False;manifest['historical_plan_source_preserved']=True
    write(path,manifest)
    print(json.dumps(dict(source_commit=SHA,report=str(OUT/'REPORT.md'),targeted=t['tests_run'],independent=review['status'],states=states)))


if __name__=='__main__':main()
