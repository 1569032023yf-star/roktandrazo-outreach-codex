"""Fixed command evidence / 固定命令证据；无生产操作。"""
from datetime import datetime,timezone
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
SOURCE='e279e5505a1526969ce1e1f4769cc11e02bce66d'
BASE='2c17b8cdb7f23eea3fa7b6ca50e3588924f4ac37'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
 tests=load(HERE/'fixed-validation/TARGETED.json');review=load(HERE/'INDEPENDENT_RESULT.json')
 package=load(HERE/'package/BUILD.json');comparison=load(HERE/'comparison/COMPARISON.json')
 assert tests['source_commit']==review['source_commit']==package['source_commit']==comparison['candidate_commit']==SOURCE
 assert tests['passed'] and not any(tests[k] for k in ('failures','errors','skips'))
 assert review['status']=='OFFLINE_SCOPED_REVIEW_PASSED'
 assert comparison['complete']
 names=subprocess.check_output(['git','diff','--name-only',BASE,SOURCE],cwd=ROOT,text=True).splitlines()
 files=[]
 for name in names:
  raw=(ROOT/name).read_bytes();blob=subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT)
  assert raw.replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n')
  files.append(dict(path=name,actual_sha256=hashlib.sha256(raw).hexdigest(),git_blob_sha256=hashlib.sha256(blob).hexdigest(),normalized_match=True))
 save(HERE/'SOURCE_MANIFEST.json',dict(source_commit=SOURCE,baseline_commit=BASE,files=files))
 # Include every actual staged package file, not only selected executables.
 artifact_files=[]
 for path in sorted((HERE/'package').rglob('*')):
  if path.is_file():artifact_files.append(dict(path=path.relative_to(HERE).as_posix(),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 save(HERE/'ARTIFACT_MANIFEST.json',dict(source_commit=SOURCE,files=artifact_files))
 now=datetime.now(timezone.utc).isoformat()
 next_zh='将固定命令、同会话终态核验与原Publisher认证/seal入口接线；完成整链独审和生命周期验收后才申请安装授权。不得将工程包当作可安装发布版。'
 next_en='Wire the fixed command and same-session terminal verifier into the original authenticated/sealed Publisher entry. Complete full-chain review and lifecycle acceptance before requesting installation authorization. The engineering archive is not an installable release.'
 record=dict(source_commit=SOURCE,updated_at=now,report=HERE.relative_to(ROOT).as_posix()+'/REPORT.md',tests=tests,
  independent_review=review['status'],independent_tests=review['independent_tests'],independent_additional_probes=review['additional_isolated_probes'],
  description_zh='固定内部命令、持久输入句柄及同源只读终态观察器已实现；原认证/seal接线和完整可安装交付仍未完成。',
  description_en='Fixed internal commands, persistent input handles and the same-source read-only terminal observer are implemented; original authentication/seal wiring and complete installable delivery remain incomplete.',
  fixed_command_component_implemented=True,input_pins_implemented=True,observer_component_connected=True,
  process_adapter_complete=False,independent_final_verifier_complete=False,complete_call_chain_review_passed=False,formal_maintenance_integrated=False,
  development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,
  allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,inventory_id='1784775229336',
  current_full_regression=comparison,current_package=package,installable_release=False,next_action=next_en,next_action_zh=next_zh)
 save(HERE/'RESULT.json',record)
 for rel in ('autonomy/AUTONOMOUS_TASK_QUEUE.json','autonomy/runtime/queue.json'):
  p=ROOT/rel;value=load(p);task=next(t for t in value['tasks'] if t['id']=='A-unattended-architecture-20261026')
  task.update(candidate_commit=SOURCE,updated_at=now,status='in_progress',checkpoint=record['report'],targeted_tests=tests['tests_run'],review_status=review['status'],
   full_regression=comparison,u1_install_command_latest=record,next_action=next_en,next_action_en=next_en,next_action_zh=next_zh,
   allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False)
  value.update(u1_install_command_latest=record,checkpoint=record['report'],updated_at=now)
  save(p,value)
 n=review['independent_tests']['count'];seconds=review['independent_tests']['duration_seconds'];probes=len(review['additional_isolated_probes'])
 text=f'''# U1 固定命令、输入保护与终态接线 / Fixed command, input protection and terminal wiring

固定源码 / Fixed source: `{SOURCE}` | {now}

## 实际完成 / Implemented

原Inventory到Publisher的维护互斥实现继续保留。本次增加受信内部固定安装命令：release ID不能携带路径；独立批准源码、manifest、runtime plan、PowerShell镜像和生成配置摘要；安装、升级、显式恢复和回滚命令参数固定，不能接受任意命令。包与引用文件以拒写/拒删句柄持续固定，父目录禁止重命名；终态核验完成前不能关闭保护。包脚本集合精确9项。
The existing Inventory-to-Publisher maintenance exclusion remains intact. This change adds a trusted internal fixed installer command: release IDs cannot contain paths; independent approval binds source, manifest, runtime plan, PowerShell image and generated configuration hashes. Installation, upgrade, explicit recovery and rollback use fixed arguments without arbitrary commands. Deny-write/delete file handles and non-renamable ancestor handles remain open through terminal verification. The package script set contains exactly nine members.

普通包文件拒绝硬链接。Windows系统组件存在服务维护硬链接，因此仅既有六个.NET固定路径与固定System32 PowerShell引用允许系统硬链接，并仍固定批准摘要、文件身份、字节和规范路径。原生探针验证别名写入遭拒；Windows允许移除另一个别名，这不删除已固定规范路径，也不改变内容。不能宣称所有别名均不可删除。
Ordinary package files reject hard links. Windows servicing uses hard links for system components, so only the existing six fixed .NET paths and fixed System32 PowerShell reference allow them, while retaining approved hashes, identities, bytes and canonical names. Native probes verify alias writes are denied. Windows permits removal of another alias without deleting the pinned canonical name or changing its content; universal alias-deletion prevention is not claimed.

公开Install-DisabledHost.ps1的Execute仍在加载helper之前硬拒绝。共享准备函数与私有Publisher入口先核对原维护RPC授权，缺少父进程确认即拒绝，不读取包或创建目标。过期runtime凭据阻止正向安装/升级；显式补偿仍需原维护权，不因过期凭据被困住。固定只读观察器复用同批受保护脚本和PowerShell镜像，绑定操作编号/随机挑战值并持续核验维护权，再接独立InstallVerifier。未使用ExecutionPolicy Bypass或修改系统执行策略。
Public Execute still rejects before loading helpers. Shared preparation and the private Publisher entry require the original maintenance RPC acknowledgment first; without it they refuse before package reads or target creation. Expired runtime credentials block forward install/upgrade; explicit compensation still requires the original maintenance authority without being trapped by credential expiry. The fixed read-only observer uses the same pinned scripts/PowerShell image, binds operation ID and random challenge, continually verifies maintenance ownership and feeds InstallVerifier. No execution-policy bypass or policy change was introduced.

## 测试与独审 / Tests and independent review

固定源码组合：**{tests['tests_run']}项通过，{tests['seconds']}秒，0 failures/errors/skips**。独立审核：**{n}项通过，{seconds}秒，另{probes}个隔离探针**。详情见fixed-validation与INDEPENDENT_REVIEW.md。仅为OFFLINE_SCOPED_REVIEW_PASSED，不是完整调用链审核。
Fixed-source combined validation: **{tests['tests_run']} passed in {tests['seconds']} seconds, zero failures/errors/skips**. Independent review: **{n} passed in {seconds} seconds plus {probes} isolated probes**. See fixed-validation and INDEPENDENT_REVIEW.md. Approval is scoped offline review, not complete-call-chain approval.

开发过程如实记录：最初PowerShell系统硬链接导致1项error，按上述既有固定系统引用修正；两个探针原先分别错误假定Python CRT必有winerror=32、所有别名删除都受阻，已改用原生Windows写句柄与规范路径身份/内容验证。初始efe78a1独审21项中1项error：配置测试仍从旧脚本提取已移动正文，现修复读取真实共享准备脚本，e279重新运行全部组合和独审。旧validation目录为开发尝试，期间测试文件发生修正，不能作为固定e279证据；权威结果仅fixed-validation。
Development diagnostics are retained honestly: the initial PowerShell system hard link caused one error, corrected using the fixed system-reference handling above. Two probes incorrectly assumed Python CRT always exposes winerror=32 and that every alias removal is denied; native Windows write handles and canonical identity/content checks replaced those assumptions. Initial efe78a1 review had one error among 21 tests because configuration extraction read the former script. It now reads the actual shared preparation script; all combined and independent tests were rerun on e279. The old validation folder is a development attempt during which that test changed and cannot establish fixed e279 evidence; fixed-validation is authoritative.

可比全量回归基线 `{comparison['baseline_commit']}`、候选 `{SOURCE}`：基线{comparison['baseline_run']}项，{comparison['baseline_failures']} failures、{comparison['baseline_errors']} errors；候选{comparison['candidate_run']}项，{comparison['candidate_failures']} failures、{comparison['candidate_errors']} errors。失败ID一致={comparison['failure_ids_identical']}，错误ID一致={comparison['error_ids_identical']}，NO_NEW_REGRESSION={comparison['no_new_regression']}，ALL_GREEN={comparison['all_green']}。这不是全部通过。
Comparable full regression baseline `{comparison['baseline_commit']}`, candidate `{SOURCE}`: baseline {comparison['baseline_run']} tests with {comparison['baseline_failures']} failures/{comparison['baseline_errors']} errors; candidate {comparison['candidate_run']} tests with {comparison['candidate_failures']} failures/{comparison['candidate_errors']} errors. Failure IDs identical={comparison['failure_ids_identical']}; error IDs identical={comparison['error_ids_identical']}; NO_NEW_REGRESSION={comparison['no_new_regression']}; ALL_GREEN={comparison['all_green']}. This is not an all-pass claim.

## 实际工程包 / Actual engineering artifacts

真实编译AMD64宿主及当前9项脚本已重建，{package['files']}个载荷文件，所有文件SHA256见ARTIFACT_MANIFEST.json；外部CPython运行时未捆绑。此包明确formal_backend_integrated=false、formal_maintenance_integrated=false、production_ready=false，公开执行硬门禁保留，**不是完整可安装发布版**。原Publisher的适配器模块尚未打包进该宿主载荷，须随原通道受审更新交付。
The actual compiled AMD64 host and current nine scripts were rebuilt with {package['files']} payload files; ARTIFACT_MANIFEST.json lists every file SHA256. External CPython is not bundled. The archive explicitly declares formal_backend_integrated=false, formal_maintenance_integrated=false and production_ready=false, retaining the public execution gate; **it is not a complete installable release**. Publisher adapter modules are not included in this host payload and require a reviewed original-channel update.

- install.zip SHA256: `{package['artifacts']['install.zip']}`
- rollback-tools.zip SHA256: `{package['artifacts']['rollback-tools.zip']}`
- package manifest SHA256: `{package['manifest_sha256']}`

## 未完成、真实安装门禁与WorkBuddy下一步 / Remaining work, real-install gates and WorkBuddy next steps

{next_zh}
{next_en}

尚未完成：原认证/seal正式接线及通道交付、正式backend事件消费者全链、完整固定候选审核、真实Windows首装/升级/安装和回滚中断恢复、无人值守验收。既有隔离文件/SQLite/Job证据继续有范围限制，SCM/ACL成功路径仍使用替身；本机Windows PowerShell -File执行策略限制未被绕过。LAUNCH-only缺少CONTAINED凭据的窗口仍为UNKNOWN/STOP_AND_PRESERVE，不自动重放。
Remaining: original authenticated/sealed admission and channel delivery, complete formal-backend event-consumer chain, full fixed-candidate review, real Windows first install/upgrade/install and rollback interruption recovery, and unattended acceptance. Existing isolated file/SQLite/Job evidence retains its limits; successful SCM/ACL paths still use doubles. Local Windows PowerShell -File policy restrictions were not bypassed. LAUNCH-only without CONTAINED remains UNKNOWN/STOP_AND_PRESERVE without automatic replay.

WorkBuddy下一步：待完整候选、审核和明确授权后，针对最终SHA验证系统PowerShell -File可按现场既有策略运行、实际服务Disabled/Stopped与服务账户、非对称ACL、安装/升级/回滚/进程退出恢复及唯一Inventory排他；不重复要求P1已提交环境证据。当前不执行这些现场动作，不手动启动Inventory。
WorkBuddy next: after the complete candidate, review and explicit authorization, verify system PowerShell -File under existing site policy, actual Disabled/Stopped service/account, asymmetric ACLs, installation/upgrade/rollback/process-exit recovery and sole-Inventory exclusion against the final SHA. Do not repeat already-consumed P1 evidence requests. None of these site actions is performed now; do not manually start Inventory.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

本轮仅离线开发与临时隔离测试，未修改生产DB/账本/ACL/目录/服务/Inventory/代理/注册表/任务/执行策略或现场发布器；接受既定非对称ACL裁决。目标继续执行。
Only offline development and temporary isolated testing were performed. No production DB, ledger, ACL, directory, service, Inventory, proxy, registry, task, execution policy or site publisher was modified. The accepted asymmetric ACL ruling remains in force. The goal remains active.
'''
 (HERE/'REPORT.md').write_text(text,encoding='utf-8')
 preface=f'''# U1 固定命令与输入保护 / Fixed command and input protection

固定源码 / Fixed source: `{SOURCE}` | {now}

组合{tests['tests_run']}项通过；独审{n}项及{probes}探针通过。真实AMD64工程包已重建，完整安装发布尚未完成。
{tests['tests_run']} combined tests passed; {n} independent tests and {probes} probes passed. Actual AMD64 engineering artifacts were rebuilt; complete installable delivery remains incomplete.

{next_zh}
{next_en}

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false`

[双语报告 / Bilingual report](../u1_install_command_20261103/REPORT.md)

---

'''
 for filename in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
  path=ROOT/'autonomy/evidence/unattended_20261026'/filename;old=path.read_text(encoding='utf-8')
  if SOURCE not in old.split('---',1)[0]:path.write_text(preface+old,encoding='utf-8')
 path=ROOT/'autonomy/evidence/unattended_20261026/RELEASE_MANIFEST.json';value=load(path)
 value.update(current_engineering_checkpoint=record,latest_engineering_commit=SOURCE,current_release_ready=False);save(path,value)

if __name__=='__main__':main()
