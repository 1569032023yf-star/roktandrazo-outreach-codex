"""Persist actual fixed-source status / 持久化实际固定源码状态。"""
from datetime import datetime,timezone
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SOURCE='6ff9f61653957eec06887030b17333153e80d1c5'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 tests=load(HERE/'validation/TARGETED.json');review=load(HERE/'INDEPENDENT_RESULT.json')
 assert tests['source_commit']==review['source_commit']==SOURCE
 assert tests['passed'] and not any(tests[k] for k in ('failures','errors','skips'))
 assert review['status']=='OFFLINE_SCOPED_REVIEW_PASSED'
 changed=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',SOURCE],cwd=ROOT,text=True).splitlines()
 files=[]
 for name in changed:
  raw=(ROOT/name).read_bytes();blob=subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT)
  assert raw.replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n')
  files.append(dict(path=name,actual_sha256=hashlib.sha256(raw).hexdigest(),git_blob_sha256=hashlib.sha256(blob).hexdigest(),normalized_match=True))
 save(HERE/'SOURCE_MANIFEST.json',dict(source_commit=SOURCE,files=files))
 now=datetime.now(timezone.utc).isoformat()
 next_zh='完成固定命令和进程身份适配、启动及终止持久凭据，并连接原认证/seal调用链；全链独审后再冻结完整安装包，进行生命周期和可比全量回归。'
 next_en='Complete pinned-command/process-identity adaptation, durable launch/termination evidence and original authentication/seal wiring; review the full chain before freezing the complete artifact and running lifecycle/comparable regression.'
 record=dict(source_commit=SOURCE,updated_at=now,report=HERE.relative_to(ROOT).as_posix()+'/REPORT.md',tests=tests,
  description_zh='独立终态核验组件已实现；真实文件及日志核验通过，SCM/ACL成功路径仍隔离替身，正式进程适配与全链未完成。',
  description_en='Independent terminal verifier implemented; actual file/journal validation passes, SCM/ACL success paths remain isolated doubles and formal process adaptation/full-chain integration remain incomplete.',
  independent_review=review['status'],independent_tests=review['independent_tests'],independent_additional_probes=review['additional_isolated_probes'],terminal_verifier_component_implemented=True,independent_final_verifier_complete=False,
  process_adapter_complete=False,complete_call_chain_review_passed=False,formal_maintenance_integrated=False,
  development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,
  allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,inventory_id='1784775229336',
  current_full_regression='NOT_RUN_FOR_THIS_SOURCE',current_package='NOT_BUILT_INCOMPLETE_INTEGRATION',next_action=next_en,next_action_zh=next_zh)
 save(HERE/'RESULT.json',record)
 for rel in ('autonomy/AUTONOMOUS_TASK_QUEUE.json','autonomy/runtime/queue.json'):
  p=ROOT/rel;value=load(p);task=next(t for t in value['tasks'] if t['id']=='A-unattended-architecture-20261026')
  task.update(candidate_commit=SOURCE,updated_at=now,status='in_progress',checkpoint=record['report'],targeted_tests=tests['tests_run'],
   review_status=review['status'],full_regression=record['current_full_regression'],u1_terminal_verifier_latest=record,
   next_action=next_en,next_action_en=next_en,next_action_zh=next_zh,allow_install=False,allow_dispatch=False,
   allow_cancel_dispatch=False,smtp_enabled=False,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False)
  save(p,value)
 text=f'''# U1 独立终态核验 / Independent terminal verification

固定源码 / Fixed source: `{SOURCE}` | {now}

## 实际工程 / Implemented engineering

终态核验器不信任安装器返回文字。原维护权持续持有期间，分别检查批准的精确文件清单和所有权凭据、实际文件 SHA、暂存文件、文件事务哈希链、安装事务绑定、根目录身份、SCM Disabled/Stopped/账户/镜像路径及非对称 ACL。两次独立观察绑定不同随机挑战，文件及日志再读保持一致，核验凭据先写入持久维护会话，再允许原会话原子释放。任何未知、篡改或不一致继续 STOP_AND_PRESERVE，不自动重放。
The verifier does not trust installer output. While original maintenance exclusion remains held, it validates the approved exact file inventory and ownership receipt, actual hashes, staging artifacts, file-journal hash chain, installation binding, root identities, Disabled/Stopped SCM identity/image and asymmetric ACL policy. Two observations use distinct challenges; files and journals are reread for consistency. Evidence is persisted in the maintenance session before its existing atomic release. Unknown, tampered or mismatching results stop and preserve exclusion without replay.

协调器 PREPARED 现在持久记录升级前根目录身份和 ACL；回滚必须恢复原有身份、原有文件/ACL，首装回滚必须恢复 ABSENT。只读 Windows 观察器固定三个目录和四种日志，不接受任意路径、命令或安装参数，并已纳入包脚本 SHA 和构建源码固定清单。公开 Execute 入口仍硬拒绝。
Coordinator PREPARED now persists prior root identities and ACLs for upgrades. Rollback must restore those identities and prior file/ACL state; fresh-install rollback must restore ABSENT. The read-only Windows observer fixes three roots and four journal names, accepts no arbitrary paths/commands/installation parameters, and is included in package script hashes and pinned build inputs. Public Execute remains hard rejected.

## 测试与独审 / Tests and independent review

固定源码组合 **{tests['tests_run']} 项通过 / {tests['seconds']} 秒**，0 failures、0 errors、0 skips。完整输出见 validation/TARGETED_OUTPUT.txt，结果见 validation/TARGETED.json。原 host/authority 分进程护栏保留。独审另行执行 **{review['independent_tests']['count']} 项通过 / {review['independent_tests']['duration_seconds']} 秒**，另 **{len(review['additional_isolated_probes'])} 个负例探针通过**。结果见 INDEPENDENT_REVIEW.md 和 INDEPENDENT_RESULT.json，仅范围审核通过，不代表完整调用链或发布就绪。
Fixed-source combined validation: **{tests['tests_run']} passed / {tests['seconds']} seconds**, zero failures/errors/skips. See validation/TARGETED_OUTPUT.txt and TARGETED.json. Host/authority process isolation remains intact. Independent execution: **{review['independent_tests']['count']} tests passed / {review['independent_tests']['duration_seconds']} seconds**, plus **{len(review['additional_isolated_probes'])} negative probes passed**. Results are in INDEPENDENT_REVIEW.md and INDEPENDENT_RESULT.json; scoped approval does not establish complete-chain approval or release readiness.

新增测试覆盖真实首装、升级、升级回滚、首装回滚、早期进程退出后的显式恢复，以及实际文件/凭据篡改、残留暂存文件、截断日志、运行中服务、错误 ACL、挑战绑定不符、未知进程终止等拒绝释放路径。实际文件、PowerShell 协调器、私有 IPC 和临时 SQLite 使用真实实现；SCM/ACL成功路径及进程身份凭据仍是隔离适配替身。Windows PowerShell 5 的真实只读 ACL 负例确认不可信临时审计目录被拒绝，不能冒称真实服务安装或 ACL 成功路径验收。
New cases cover real first-install/upgrade file transactions, upgrade/fresh rollback, explicit recovery after early process death, actual file/receipt tampering, leftover staging, torn journals, running service, incorrect ACL, challenge mismatch and unknown process termination. Files, PowerShell coordination, private IPC and temporary SQLite are real implementations; successful SCM/ACL paths and process-identity proof remain isolated adapter doubles. A real Windows PowerShell 5 read-only ACL negative probe rejects an untrusted temporary audit root. This is not real service-installation or successful Windows ACL acceptance.

开发中间失败如实保留：原8项协调器测试曾因夹具缺 Get-DaclText 失败1项，修复夹具后8项通过；新增15项首轮失败1项，因本机脚本策略阻止直接脚本运行；改为进程内代码后 Get-Acl 模块加载仍被策略阻止。观察器改用同等只读 .NET ACL 接口，未修改执行策略；最终固定源码重新运行组合验证。最初4项终态组件测试通过，不作为新候选组合证据继承。
Intermediate failures are recorded honestly: one of the original eight coordinator tests failed because the fixture lacked Get-DaclText; after fixture repair all eight passed. The first 15-test extension had one failure because local execution policy blocked direct script execution; Get-Acl module loading was also blocked when using in-process code. The observer now uses equivalent read-only .NET ACL APIs without changing execution policy. The final fixed source was rerun; the initial four passing component tests are not inherited as current combined evidence.

## 剩余工程、包与WorkBuddy / Remaining work, artifacts and WorkBuddy

{next_zh}
{next_en}

本 SHA 无新 AMD64 完整安装包及 package manifest SHA256：完整受控进程适配、持久启动/终止证明和原认证/seal接线仍未闭合；833项可比全量回归尚未重跑。旧包、旧审核和旧回归不能继承。历史37 failures、17 errors不是全绿。
No new complete AMD64 package or package-manifest SHA256 exists for this source: controlled process adaptation, durable launch/termination proof and original authentication/seal wiring remain incomplete. The comparable 833-test regression has not been rerun. Prior artifact/review/regression evidence is not inherited; historical 37 failures and 17 errors are not all green.

WorkBuddy下一步仅在完整固定候选、全链独审及授权后，验证真实Windows无人值守首装、升级、进程中断恢复、回滚中断恢复及Disabled/Stopped终态。已消费P1资料不重复索要。本阶段不执行现场安装；生产部署和业务采集验收继续位于其后。
After the complete fixed candidate, full-chain independent review and authorization, WorkBuddy should verify real unattended Windows first installation, upgrade, process-interruption recovery, interrupted rollback recovery and Disabled/Stopped terminal state. Consumed P1 evidence is not requested again. No site installation occurs at this stage; production deployment and business collection acceptance follow later.

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

本轮仅离线源码与隔离临时文件/进程/数据库；未修改生产数据库、账本、ACL、目录、服务、Inventory、代理、注册表、任务或现场发布器。接受已确定的 ACL 非对称裁决，不重开讨论。目标继续执行，不能将本组件完成描述为完整交付。
Only offline source and isolated temporary files/processes/databases were used. No production database, ledger, ACL, directory, service, Inventory, proxy, registry, task or site publisher was modified. The accepted asymmetric ACL ruling remains accepted. The goal remains active; component completion is not complete delivery.
'''
 (HERE/'REPORT.md').write_text(text,encoding='utf-8')
 preface=f'''# U1 独立终态核验 / Independent terminal verification

固定源码 / Fixed source: `{SOURCE}` | {now}

终态组件已实现，组合 {tests['tests_run']} 项通过，范围独审通过。正式进程适配、持久启动/终止凭据、原认证/seal接线与完整调用链审核仍未完成。
Terminal verifier component implemented; {tests['tests_run']} combined tests and scoped independent review passed. Formal process adaptation, durable launch/termination proof, original authentication/seal wiring and full-chain review remain incomplete.

下一步 / Next: {next_zh}

{next_en}

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false`

[双语证据 / Bilingual evidence](../u1_terminal_verifier_20261103/REPORT.md)

---

'''
 for filename in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
  path=ROOT/'autonomy/evidence/unattended_20261026'/filename;path.write_text(preface+path.read_text(encoding='utf-8'),encoding='utf-8')
 path=ROOT/'autonomy/evidence/unattended_20261026/RELEASE_MANIFEST.json';value=load(path)
 value.update(current_engineering_checkpoint=record,latest_engineering_commit=SOURCE,current_release_ready=False);save(path,value)
if __name__=='__main__':main()
