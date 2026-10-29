"""仅更新开发交接状态 / Update development handoff state only."""
import json
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
phase = read(HERE/'source/PHASE0_STATE_REFRESH_20261029.json')
receipt = dict(schema='codex.workbuddy-consumption-receipt.v1',
    summary_zh='生产证据已读取及对账；Git完整性通过，payload及调度完整性存在保留；无人登录未通过。',
    summary_en='Production evidence read and reconciled; Git integrity passed with payload and scheduler completeness reservations; login-free acceptance failed.',
    CODEX_HANDOFF_CONSUMED=False, publication_state='PREPARED_PENDING_EXISTING_ISSUE2_RECEIPT',
    consumed_at=datetime.now(timezone.utc).isoformat(),
    workbuddy_commit='5a2906104ffa89e0434fa6f8f8744fdb93347c7a',
    workbuddy_commit_at='2026-10-29T11:52:07+08:00',
    codex_remote_head_at_start='fe7ff037f9719f88cb37a78c196698c8825aa37f',
    files=read(HERE/'verification.json')['files'],
    safe=phase['safe'],inventory=phase['canonical_inventory'],cities=phase['cities'],
    bridge=phase['bridge_8791'],proxy=phase['proxy'],producer_safety=phase['safety'],
    current_task_production_database_access=False,current_task_production_database_writes=0,
    current_task_smtp_calls=0,allow_dispatch=False,allow_cancel_dispatch=False,
    unattended_accepted=False,production_evidence_accepted_without_reservations=False,
    inventory_zero_missed='PRODUCER_REPORTED_NOT_INDEPENDENTLY_FULLY_VERIFIED',
    backend_request_comment=6435605069,existing_issue=2,
    next_action_zh='继续离线版本化取消费用绑定及reserve-before-intent故障合同。',
    next_action_en='Continue offline versioned cancellation-cost binding and reserve-before-intent fault contracts.')
write(HERE/'CONSUMPTION_RECEIPT.json',receipt)
queuepath=ROOT/'autonomy/runtime/queue.json'
q=read(queuepath)
q['workbuddy_production_consumption']=receipt
for t in q['tasks']:
    if t['id']=='A-unattended-architecture-20261026':
        t['workbuddy_consumption_receipt']='autonomy/evidence/workbuddy_consumption_20261029/CONSUMPTION_RECEIPT.json'
        t['production_evidence_consumed']=True
        t['unattended_accepted']=False
        t['allow_dispatch']=False
        t['allow_cancel_dispatch']=False
        t['checkpoint']='autonomy/evidence/unattended_20261026/U1_CURRENT_CHECKPOINT.md'
    if t['id']=='A-lake-natural-acceptance-20261023':
        t['blocked_reason']='NATURAL_EVIDENCE_CONSUMED_WITH_INTEGRITY_AND_COMPLETENESS_RESERVATIONS'
        t['next_action']='Retain scoped natural-run observations; reconcile existing handoff payload and scheduler discrepancies without manual collection or production mutation.'
write(queuepath,q)
p=read(ROOT/'autonomy/AUTONOMOUS_TASK_QUEUE.json')
p['tasks']=q['tasks']
p['updated_at']=receipt['consumed_at']
p['workbuddy_production_consumption']=receipt
write(ROOT/'autonomy/AUTONOMOUS_TASK_QUEUE.json',p)
