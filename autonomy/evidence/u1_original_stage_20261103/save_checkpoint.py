"""同步固定候选证据 / Synchronize pinned evidence; no deployment."""
import json
from pathlib import Path
from datetime import datetime, timezone
import subprocess,hashlib
ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent
SOURCE='3fbaa5ec42cb0655ecd1c811ccd8d02b1fc837bb'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 t=load(HERE/'validation/TARGETED.json'); c=load(HERE/'comparison/COMPARISON.json')
 r=load(HERE/'review-3fbaa5e/INDEPENDENT_RESULT.json'); a=load(HERE/'review-3fbaa5e/INDEPENDENT_PACKAGE_RESULT.json')
 p=load(HERE/'package/BUILD.json'); o=load(HERE/'OWNER_PACKAGE.json')
 assert all(v['source_commit']==SOURCE for v in (t,r,a,p,o))
 assert t['passed'] and c['candidate_commit']==SOURCE and c['complete']
 assert r['status']=='OFFLINE_SCOPED_REVIEW_PASSED'
 assert a['status']=='OFFLINE_SCOPED_ARTIFACT_VERIFICATION_PASSED'
 p=dict(p,independent_review=a['status'],review_evidence='review-3fbaa5e/INDEPENDENT_PACKAGE_RESULT.json')
 now=datetime.now(timezone.utc).isoformat(); report=HERE.relative_to(ROOT).as_posix()+'/REPORT.md'
 next_zh='完成正式Provider执行、费用实测和受信运行配置，随后对完整候选审核；经授权后由WorkBuddy进行隔离Windows首次安装、升级、进程退出恢复、回滚中断恢复及Disabled/Stopped验收。不得用测试worker或SAFE替身代替业务验收。'
 next_en='Complete formal Provider execution, measured costs and trusted runtime configuration, then review the complete candidate. After authorization, WorkBuddy verifies isolated Windows first installation, upgrade, process-exit recovery, interrupted rollback and Disabled/Stopped state. Test workers and SAFE fixtures are not business acceptance.'
 record=dict(source_commit=SOURCE,updated_at=now,report=report,tests=t,current_full_regression=c,independent_review=r['status'],independent_tests=r['independent_tests'],package_review=a,current_package=p,owner_package=o,original_stage_event_consumer_connected=True,original_owner_identity_event_adapter_integrated=True,original_job_terminal_and_release_atomic=True,formal_backend_integrated=False,installable_release=False,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,inventory_id='1784775229336',next_action=next_en,next_action_zh=next_zh)
 save(HERE/'RESULT.json',record)
 source=[]
 for name in subprocess.check_output(['git','diff','--name-only','68788653c848659c63f85021075fedee4aca5b13',SOURCE],cwd=ROOT,text=True).splitlines():
  if not name.endswith('.py') or '/evidence/' in name:continue
  blob=subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT)
  assert blob.replace(b'\r\n',b'\n')==(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
  source.append(dict(path=name,git_blob_sha256=hashlib.sha256(blob).hexdigest()))
 save(HERE/'SOURCE_MANIFEST.json',dict(source_commit=SOURCE,files=source))
 body=f'''# U1 原执行链交付 / Original execution-chain delivery

固定源码 / Fixed source: `{SOURCE}`

中文：已将原stage接入持有既有Inventory权利的事件消费者，路径为原stage→HTTP→原owner适配器→受控子进程→预算结算→原job终态与释放同事务。错误owner、日期、原DB身份及非running任务均在调用backend前拒绝。子进程运行期间持续检查原owner，丢权时终止进程树并保留UNKNOWN。未知收据或丢ACK不重放、不回落旧业务入口。

English: The original stage now consumes events under its existing Inventory authority: original stage → HTTP → original-owner adapter → controlled child → budget settlement → atomic original-job finalization and release. Incorrect owner, date, DB identity or non-running jobs are rejected before backend invocation. Runtime owner loss stops the process tree and preserves UNKNOWN. Unknown receipts and lost ACKs authorize neither replay nor fallback to the legacy body.

中文：独审发现的先提交job成功、后发现释放失败问题已修复。写入失败及释放零行均回滚整个事务；原job保持running、原锁保留、backend只执行一次。实际进程树控制已测试；业务worker、签名及SAFE库存计数仍为隔离fixture，正式Provider和真实费用合同尚未接通。

English: Independent review found premature job success before release verification. Both job-write failure and a zero-row release now roll back the complete transaction, preserving the running job and original lock with only one backend invocation. Real process-tree control was tested; business workers, signatures and SAFE counts remain isolated fixtures. Formal Provider execution and measured-cost contracts remain incomplete.

组合测试 / Combined tests: {t['tests_run']} tests; passed={t['passed']}; failures={len(t['failures'])}; errors={len(t['errors'])}; skips={len(t['skips'])}. 每项结果见validation；新候选重新运行。 / Per-test output is under validation; this candidate was rerun.

独立审核 / Independent review: {r['status']}; {r['independent_tests']}. 详见review-3fbaa5e，旧候选失败报告保留。 / See review-3fbaa5e; previous failed-candidate reports are retained.

可比全量 / Comparable full regression: baseline `{c['baseline_commit']}` / candidate `{SOURCE}`; tests {c['baseline_run']}/{c['candidate_run']}; failures {c['baseline_failures']}/{c['candidate_failures']}; errors {c['baseline_errors']}/{c['candidate_errors']}; NO_NEW_REGRESSION={c['no_new_regression']}; ALL_GREEN={c['all_green']}. 不宣称全绿。 / No all-green claim.

真实AMD64工程包 / Actual AMD64 engineering package: {p['files']} payload files.
- install.zip SHA256: `{p['artifacts']['install.zip']}`
- rollback-tools.zip SHA256: `{p['artifacts']['rollback-tools.zip']}`
- host manifest SHA256: `{p['manifest_sha256']}`
- 17-file companion SHA256: `{o['artifact_sha256']}`
- companion manifest SHA256: `{o['manifest_sha256']}`

中文：每文件摘要见ARTIFACT_MANIFEST.json；独立包审核见review-3fbaa5e。配套包只含固定路径源码，不是更新器，不扩大旧Publisher白名单；expected_before来自固定Git基线，不是现场证据。未捆绑外部CPython及完整业务依赖，不是完整可安装发布版。

English: ARTIFACT_MANIFEST.json records per-file digests; review-3fbaa5e contains independent package checks. The companion includes fixed source paths only; it is not an updater and does not expand the old Publisher allowlist. expected_before comes from a pinned Git baseline, not site evidence. External CPython and complete business dependencies are not bundled; this is not a complete installable release.

待完成及真实安装门禁 / Remaining engineering and installation gates:
{next_zh}

{next_en}

中文：本轮未安装/启动服务、未修改生产ACL/数据库/账本/Inventory。现有安装器事务测试不等同于WorkBuddy真实Windows无人值守成功验收。保留已接受的非对称ACL裁决。

WorkBuddy后续具体核验（完整候选审完且另行授权后） / Specific later WorkBuddy checks (after complete-candidate review and separate authorization):
1. 隔离Windows核对固定commit、安装包/manifest/运行时身份；保留安装前文件和ACL快照。 / In isolated Windows, verify commit, archive/manifest/runtime identities and retain pre-install file/ACL snapshots.
2. 首装核对两个根目录的非对称ACL、自有文件收据以及服务Disabled/Stopped；升级覆盖新增、替换、删除。 / Check asymmetric root ACLs, owned-file receipts and Disabled/Stopped registration; upgrade must cover creation, replacement and deletion.
3. 在持久intent、实际写入、回执与回滚边界注入退出，再重启安装进程；ABSENT须恢复，未知状态必须STOP_AND_PRESERVE。 / Terminate at durable-intent, mutation, receipt and rollback boundaries, then restart the installer; restore ABSENT and preserve unknown states.
4. 核实维护权取得、持续持有、最终读回和精确释放；原Inventory占用或UNKNOWN时不得取得安装权。 / Verify maintenance acquisition, continuous holding, final readback and exact release; a held/UNKNOWN original Inventory must deny installation authority.
5. 不触发生产Inventory；无人值守业务验收必须待正式Provider链与独立授权完成，单独记录实际请求、费用、取消和结算证据。 / Do not trigger production Inventory; unattended business acceptance awaits the formal Provider chain and authorization, with separate actual request, cost, cancellation and settlement evidence.

English: No service was installed/started and no production ACL, DB, ledger or Inventory was modified. Installer transaction tests do not establish WorkBuddy's real Windows unattended acceptance. The accepted asymmetric ACL ruling remains unchanged.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
'''
 (HERE/'REPORT.md').write_text(body,encoding='utf-8')
 for rel in ('autonomy/AUTONOMOUS_TASK_QUEUE.json','autonomy/runtime/queue.json'):
  path=ROOT/rel; v=load(path); task=next(x for x in v['tasks'] if x['id']=='A-unattended-architecture-20261026')
  task.update(candidate_commit=SOURCE,status='in_progress',updated_at=now,checkpoint=report,targeted_tests=t['tests_run'],review_status=r['status'],full_regression=c,u1_original_stage_latest=record,next_action=next_en,next_action_en=next_en,next_action_zh=next_zh)
  v.update(u1_original_stage_latest=record,checkpoint=report,updated_at=now);save(path,v)
 for name in ('U1_CURRENT_CHECKPOINT.md','U1_DELIVERY_STATUS.md'):
  (ROOT/'autonomy/evidence/unattended_20261026'/name).write_text(body,encoding='utf-8')
 path=ROOT/'autonomy/evidence/unattended_20261026/RELEASE_MANIFEST.json';v=load(path)
 v.update(u1_original_stage_latest=record,current_engineering_source_commit=SOURCE,installable_release=False,development_complete=False,release_ready=False,production_deployed=False,production_accepted=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False);save(path,v)
 print(json.dumps(dict(source_commit=SOURCE,tests=t['tests_run'],review=r['status'])))
if __name__=='__main__':main()
