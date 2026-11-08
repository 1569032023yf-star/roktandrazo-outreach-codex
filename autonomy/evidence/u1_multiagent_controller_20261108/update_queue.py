"""Append scoped next-cycle work to the existing queue under its own lock."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from autonomy.supervisor import atomic_json, exclusive, read

root = Path(__file__).resolve().parents[3]
runtime = root / 'autonomy' / 'runtime'
path = runtime / 'queue.json'
items = [
    dict(id='A-u1-owner-intent-status-review-20261108', workstream='A',
         source_commit='d76eb049967f3f9811af46db0a73a3a9685d497a',
         scope_zh='针对已记录 Owner 事件意图但槽位和预算尚不存在的中断，核实请求状态不得误报未记录；补真实 SQLite 与 Owner 离线回归，保持未知状态和重放门禁。',
         scope_en='Investigate an owner event intent followed by interruption before slot and budget records; add an offline real SQLite and Owner regression and preserve unknown/replay gates.',
         next_action='Independently reproduce with a real Owner and local SQLite, fix conservatively, test, and submit a pinned reviewable commit.'),
    dict(id='B-u1-host-cleanup-stage-review-20261108', workstream='B',
         source_commit='29e9ef5cebc68c69e84b881f808314e6d712c6a2',
         scope_zh='离线覆盖 Host 清理失败、对象丢失与回收及启动停止失败；分段诊断暂存超时、验证恢复，固定新源码后重新审查打包。',
         scope_en='Cover host cleanup failure, lost references and GC, and startup/stop failure offline; profile staging timeout phases, validate recovery and review a newly pinned package.',
         next_action='Preserve existing untracked candidate, reproduce failure paths and time staging phases; provide evidence and a pinned reviewable commit.'),
]
with exclusive(runtime):
    state = read(path)
    if not isinstance(state, dict) or not isinstance(state.get('tasks'), list):
        raise RuntimeError('CANONICAL_QUEUE_REQUIRED')
    before = sha256(path.read_bytes()).hexdigest()
    existing = {t.get('id') for t in state['tasks']}
    added = []
    for item in items:
        if item['id'] in existing:
            continue
        item.update(role='developer', status='pending', attempts=0, blocked_cycles=0,
                    outcome_unknown=False, executor='not_started',
                    production_execution=False, allow_dispatch=False,
                    release_ready=False, review_status='NOT_STARTED')
        state['tasks'].append(item)
        added.append(item['id'])
    if added:
        state['updated_at'] = datetime.now(timezone.utc).isoformat()
        atomic_json(path, state)
    check = read(path)
    for item in items:
        matches = [t for t in check['tasks'] if t.get('id') == item['id']]
        if len(matches) != 1 or matches[0].get('status') != 'pending':
            raise RuntimeError('QUEUE_READBACK_FAILED')
    print('before_sha256=' + before)
    print('after_sha256=' + sha256(path.read_bytes()).hexdigest())
    print('added=' + ','.join(added))
    print('status=pending; execution=not_started')
