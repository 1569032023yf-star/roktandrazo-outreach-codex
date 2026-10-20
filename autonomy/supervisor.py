"""Bounded development queue. Never imports the production application.

开发任务队列；不得采集生产客户或发送邮件。
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

try:
    from autonomy.process_job import run_tree
except ModuleNotFoundError:
    from process_job import run_tree

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'autonomy' / 'runtime'
LOCAL_TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def exclusive(runtime):
    """Fail closed on an orphan lock: explicit recovery audits it first."""
    runtime.mkdir(parents=True, exist_ok=True)
    lock = runtime / 'supervisor.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump({'pid': os.getpid(), 'started_at': now()}, handle)
        yield
    finally:
        lock.unlink()


def _init_locked(runtime):
    if not (runtime / 'queue.json').exists():
        atomic_json(runtime / 'queue.json', {
            'schema_version': 1,
            'description_zh': '独立开发队列；不启动正式客户采集。',
            'description_en': 'Independent development queue; never starts production discovery.',
            'tasks': [{'id': 'D-supervisor-independent-review', 'workstream': 'D',
                       'status': 'queued', 'attempts': 0, 'role': 'reviewer',
                       'blocked_cycles': 0},
                      {'id': 'D-sanitized-telemetry-adapter', 'workstream': 'D',
                       'status': 'queued', 'attempts': 0, 'role': 'developer',
                       'blocked_cycles': 0}], 'cycles': []})


def init(runtime=RUNTIME):
    with exclusive(runtime):
        _init_locked(runtime)


def reconcile(runtime, state):
    # queue.json is the authoritative write-ahead record; restore missing receipts.
    for record in state['cycles']:
        if record['status'] != 'running':
            atomic_json(runtime / 'cycles' / (record['cycle_id'] + '.json'), record)


def task_prompt(task):
    # Queue data never becomes executable commands or arbitrary agent instructions.
    if task['id'] == 'D-storage-failure-audit' and task['role'] == 'reviewer':
        return ('独立只读审核autonomy/supervisor.py和process_job.py的磁盘满失败路径。'
                '先读AGENTS.md及docs/AUTONOMY_BRAND_INTEGRATION.md。已发生ENOSPC导致完成记录未落盘，'
                '后续手动恢复后CLI又超时；分别分析，不推测相同原因。核查启动前空间检查、'
                '原子写失败、租约恢复、未知结果不重执行有副作用操作、临时输出上限及进程清理。'
                '只读源码与脱敏周期记录，不读凭据、原始候选或生产DB，不联网、不修改文件。'
                '列最小可测试修复方案和限制，不创建调度器、不擅自清理用户文件。'
                '最终仅JSON summary_zh、summary_en、findings数组，每项severity/file/detail_zh/detail_en。')
    if task['id'] == 'B-brand-package-integration' and task['role'] == 'developer':
        return ('你是独立Developer，执行已授权的有界品牌代码迁移。先读AGENTS.md、总控文档及'
                'docs/AUTONOMY_BRAND_DEPENDENCY_AUDIT.md。来源严格固定Git提交'
                '5e9b89de99a596b509426a596ef02fcc7521facc，不联网、不采集、不读候选原始数据或生产DB/凭据。'
                '只允许新增该提交brand_acquisition目录的15个Python源码文件；新增以下6个原测试：'
                'tests/test_brand_acquisition.py、test_brand_acquisition_offline.py、test_directory_live_layouts.py、'
                'test_directory_live_preflight.py、test_industry_directory_acquisition.py、test_phase4b1g_site_conversion.py；新增以下4个原入口：'
                'scripts/run_brand_acquisition_canary.py、run_brand_capture.py、run_industry_directory_canary.py、run_official_site_conversion.py。'
                '全部从固定Git对象取原始内容。已存在且内容相同可跳过，若不同必须停止该路径并报告，禁止覆盖。'
                '不修改任何现有共享源码、城市/V6门禁、配置、队列或验收状态；不迁移runtime/output/真实数据。'
                '只能运行原六个测试模块及必要既有5A/隔离启动回归的离线合成测试，禁止运行任何采集脚本或实际DNS/HTTP/SMTP；'
                '设置CODEX_SANDBOX_NETWORK_DISABLED=1并使用开发护栏，任何真实联网需求改报告阻塞。'
                '逐项核对既有discovery服务API兼容；不靠复制旧共享文件解决差异。'
                '可另新增docs/AUTONOMY_BRAND_INTEGRATION.md双语报告，列迁移文件、来源哈希、真实测试、'
                '缺失依赖、未执行与风险；10分钟到时保留工作退出，不自行提交或标记审核通过。'
                '最终仅JSON summary_zh、summary_en、findings数组。')
    if task['id'] == 'B-brand-integration-review' and task['role'] == 'reviewer':
        return ('你是独立Reviewer，只读审查品牌迁移差异和docs/AUTONOMY_BRAND_INTEGRATION.md。'
                '核对新增brand_acquisition、对应六测试及四scripts是否来自固定提交'
                '5e9b89de99a596b509426a596ef02fcc7521facc；既有5A/城市/V6源码是否保持，'
                '历史UNKNOWN、MX、身份、预算及限制域是否未降级，离线测试证据是否真实。'
                '不修改文件，不运行采集/生产入口，不读候选原始数据、生产DB或凭据，不联网。'
                '允许纯内存合成验证，不能执行的测试如实列明。最终仅JSON summary_zh、summary_en、'
                'findings数组，每项severity/file/detail_zh/detail_en，不将迁移视作业务新增或生产发布。')
    if task['id'] == 'B-brand-dependency-audit' and task['role'] == 'reviewer':
        return ('你是独立Reviewer，执行品牌依赖迁移前的只读差异审核。先读AGENTS.md和总控文档。'
                '仅比较当前工作树与固定Git提交5e9b89de99a596b509426a596ef02fcc7521facc中的'
                'brand_acquisition、对应tests及入口scripts的导入依赖；用Git读取和AST分析，'
                '不导入或运行采集/生产模块，不联网、不读候选原始数据/生产DB/凭据，不修改文件。'
                '识别缺失模块、同名文件差异、资格/历史/MX依赖和最小可复现离线测试集。'
                '指出哪些文件可作为新增文件迁移，哪些现有文件必须精确合并，禁止整文件覆盖较新5A代码。'
                '最终仅JSON字段summary_zh、summary_en、findings数组；每项severity/file/detail_zh/detail_en。'
                '摘要列出已核查范围、未验证限制和下一项最小代码修改。不把目录存在当作身份或发信资格。'
                '预算10分钟，读不到固定提交则报告阻塞，不猜测替代提交。')
    if task['id'] == 'D-sanitized-telemetry-adapter' and task['role'] == 'developer':
        return ('你是独立Developer，执行用户已授权的一项有界工程任务。先读AGENTS.md和总控文档。'
                '只允许新建或编辑autonomy/telemetry.py、autonomy/test_telemetry.py、'
                'docs/AUTONOMY_TELEMETRY_CONTRACT.md，不修改其他源码/队列/验收状态。'
                '实现读取autonomy/runtime/telemetry/inbox内获准脱敏快照的严格校验器，'
                '只接收聚合计数、来源、采集时间、明确24h/7d区间、去重快照ID；拒绝未来时间、'
                '过期、重复、负数、身份邮箱/凭据字段和无来源数据。没有有效输入返回UNKNOWN，'
                '不把历史累计计为当日新增。只有本地合成fixture测试，不读取生产数据库/凭据，'
                '不访问WorkBuddy，不联网不发信，不创建采集调度器。不得在没有真实feed时声称'
                '遥测已接通。为失败路径编写必要测试并运行。报告中英双语，最终仅返回JSON，'
                '字段summary_zh、summary_en、findings数组；摘要列出真实测试结果和未完成限制。'
                '时间预算10分钟，到时保留源码并退出。父代理将独立审查，不能自行标验收完成。')
    if task['id'] == 'D-telemetry-independent-review' and task['role'] == 'reviewer':
        return ('你是独立Reviewer，只读审查autonomy/telemetry.py、autonomy/test_telemetry.py、'
                'docs/AUTONOMY_TELEMETRY_CONTRACT.md，独立运行合成输入的离线测试。'
                '核对时间区间、数据来源、重复、UNKNOWN和无生产副作用。不要修改文件，不读凭据'
                '或生产DB，不联网。最终仅JSON字段summary_zh、summary_en、findings数组，'
                '每项severity/file/detail_zh/detail_en。无问题findings为空。不声称真实feed已接通。')
    if task['id'] != 'D-supervisor-independent-review' or task['role'] != 'reviewer':
        raise ValueError('UNREGISTERED_TASK')
    return ('你是独立Reviewer，仅只读检查本工作树 autonomy/supervisor.py、'
            'autonomy/test_supervisor.py、docs/CODEX_AUTONOMOUS_BD_OPERATING_SYSTEM.md。'
            '检查锁、超时、崩溃恢复、调度证据、任务队列与生产隔离失败路径。'
            '不运行生产模块，不读凭据、生产数据库，不发网络请求，不编辑文件。'
            '最终仅返回JSON对象，字段summary_zh、summary_en、findings（数组，每项含'
            'severity、file、detail_zh、detail_en），无问题时findings为空。'
            '不要把探针成功或定时器创建当成两次自主开发周期已验收。')


def run_agent(task, root, timeout=600):
    exe = shutil.which('codex')
    if not exe:
        return {'ok': False, 'reason': 'CODEX_NOT_FOUND'}
    prompt = task_prompt(task)
    sandbox = 'workspace-write' if task['role'] == 'developer' else 'read-only'
    args = [exe, '-a', 'never', 'exec', '-s', sandbox, '--ephemeral',
            '--json', '-C', str(root), prompt]
    try:
        result = run_tree(args, timeout=timeout, cwd=root)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'reason': 'AGENT_TIMEOUT'}
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    messages = [e['item']['text'] for e in events if e.get('type') == 'item.completed'
                and e.get('item', {}).get('type') == 'agent_message']
    completed = any(e.get('type') == 'turn.completed' for e in events)
    if result.returncode or not completed or not messages:
        return {'ok': False, 'reason': 'AGENT_INCOMPLETE', 'exit_code': result.returncode}
    final = messages[-1].strip()
    if final.startswith('```'):
        final = '\n'.join(final.splitlines()[1:-1])
    try:
        report = json.loads(final)
        valid = (isinstance(report, dict) and isinstance(report.get('findings'), list)
                 and isinstance(report.get('summary_zh'), str)
                 and isinstance(report.get('summary_en'), str))
        if not valid:
            raise ValueError('INVALID_REVIEW_SCHEMA')
    except (ValueError, TypeError):
        return {'ok': False, 'reason': 'INVALID_REVIEW_SCHEMA'}
    return {'ok': True, 'reason': 'REVIEW_COMPLETED', 'report': report,
            'output_sha256': hashlib.sha256(result.stdout.encode()).hexdigest()}


def cycle(runtime=RUNTIME, root=ROOT, source='manual', runner=run_agent):
    if source not in {'manual', 'codex_heartbeat'}:
        raise ValueError('INVALID_SOURCE')
    with exclusive(runtime):
        _init_locked(runtime)
        state = read(runtime / 'queue.json')
        reconcile(runtime, state)
        # A prior worker may have died after persisting a running lease.
        for task in state['tasks']:
            if task['status'] == 'running':
                task.update(status='blocked' if task['attempts'] >= 3 else 'queued',
                            recovery_reason='PRIOR_CYCLE_INTERRUPTED',
                            blocked_cycles=task.get('blocked_cycles', 0) + 1)
                task['needs_reassessment'] = task['blocked_cycles'] >= 2 or task['status'] == 'blocked'
                for prior in state['cycles']:
                    if prior['cycle_id'] == task.get('lease_cycle_id') and prior['status'] == 'running':
                        prior.update(status='interrupted', finished_at=now())
        reconcile(runtime, state)
        eligible = [t for t in state['tasks'] if t['status'] == 'queued' and t['attempts'] < 3]
        record = {'cycle_id': str(uuid.uuid4()), 'source': source, 'started_at': now(),
                  'status': 'idle', 'task_id': None, 'human_trigger_excluded': source == 'manual'}
        state['cycles'].append(record)
        if eligible:
            task = eligible[0]
            task.update(status='running', attempts=task['attempts'] + 1,
                        lease_cycle_id=record['cycle_id'])
            record.update(status='running', task_id=task['id'])
            atomic_json(runtime / 'queue.json', state)
            try:
                outcome = runner(task, root)
            except Exception as error:
                # Never serialize exception messages, prompts or environment secrets.
                outcome = {'ok': False, 'reason': 'RUNNER_EXCEPTION', 'type': type(error).__name__}
            task['status'] = ('needs_review' if task['role'] == 'developer' else 'completed') if outcome['ok'] else ('blocked' if task['attempts'] >= 3 else 'queued')
            reviews = {'D-sanitized-telemetry-adapter': ('D', 'D-telemetry-independent-review'),
                       'B-brand-package-integration': ('B', 'B-brand-integration-review')}
            if outcome['ok'] and task['id'] in reviews:
                workstream, review_id = reviews[task['id']]
                if not any(t['id'] == review_id for t in state['tasks']):
                    state['tasks'].append({'id': review_id, 'workstream': workstream,
                        'status': 'queued', 'attempts': 0, 'role': 'reviewer', 'blocked_cycles': 0})
            task['blocked_cycles'] = 0 if outcome['ok'] else task.get('blocked_cycles', 0) + 1
            task['needs_reassessment'] = task['blocked_cycles'] >= 2
            record.update(status='completed' if outcome['ok'] else 'failed', outcome=outcome)
        record['finished_at'] = now()
        atomic_json(runtime / 'queue.json', state)
        atomic_json(runtime / 'cycles' / (record['cycle_id'] + '.json'), record)
        return record


def two_unattended_cycles(records):
    """Conservative: idle, manual, failed or closely spaced runs never qualify.

    Source labels alone are not authenticity proof. The app's two trigger receipts
    must be independently matched before promoting the validation flag.
    """
    return False


def dashboard(root=ROOT):
    """Unknown is not zero; there is no approved production telemetry feed yet."""
    unknown = 'UNKNOWN'
    metrics = {key: unknown for key in ('NEW_VERIFIED_ORGANIZATIONS_24H',
        'NEW_FIRST_PARTY_EMAILS_24H', 'SAFE_TOTAL_LATEST', 'SAFE_NET_GROWTH_7D',
        'CUSTOMER_EMAILS_SENT_24H', 'REPLIES_24H', 'BOUNCES_24H', 'UNSUBSCRIBES_24H',
        'NEW_VERIFIED_ORGANIZATIONS_7D', 'NEW_FIRST_PARTY_EMAILS_7D',
        'CUSTOMER_EMAILS_SENT_7D', 'REPLIES_7D', 'BOUNCES_7D', 'UNSUBSCRIBES_7D',
        'OFFICIAL_SITES_24H', 'OFFICIAL_SITES_7D', 'HISTORY_MX_VERIFIED_24H',
        'HISTORY_MX_VERIFIED_7D', 'ACTIVE_CITY')}
    state = read(root / 'autonomy' / 'WORKSTREAM_STATUS.json', {})
    control = state.get('workstreams', {}).get('D', {})
    next_zh = control.get('next_automatic_action_zh', unknown)
    next_en = control.get('next_automatic_action_en', unknown)
    report = ['# ROKT&RAZO 业务日报 / Business Daily Report', '',
              '日期 / Date: ' + datetime.now(LOCAL_TZ).date().isoformat(), '',
              '生产指标未接入获准脱敏数据源，UNKNOWN不能当成零或历史累计。',
              'Production telemetry has no authorized sanitized feed; UNKNOWN is neither zero nor a historical total.', '',
              f"成功无人值守周期 / Successful unattended cycles: {control.get('successful_unattended_cycles', unknown)}；整体自主运行尚未验收 / Overall autonomy not accepted.", '',
              '| 今日业务问题 / Daily business question | 结果 / Result |', '|---|---|',
              '| 新增真实组织 / New real organizations | UNKNOWN；B本轮0 / B current run: 0 |',
              '| 新增第一方邮箱 / New first-party emails | UNKNOWN；B本轮0 / B current run: 0 |',
              '| SAFE总量及增长 / SAFE total and growth | UNKNOWN |',
              '| 活动城市 / Active city | UNKNOWN；城市修复开发验证与生产状态分开 / Development validation is separate from production state |',
              '| V6和发信缺口 / V6 and sending gaps | 新QA登记、收件认证、客户地址及全资格门禁 / New QA registration, receipt/authentication, customer address and full eligibility gates |',
              '| 本轮生产部署 / Production releases this run | 0；当日其他发布UNKNOWN / 0; other releases today UNKNOWN |',
              '| 阻塞 / Blockers | 新发布入口、历史副本、遥测待接通 / New release entrypoint, history copy and telemetry unavailable |',
              f'| 下一步 / Next | {next_zh} / {next_en} |', '',
              '| 指标 / Metric | 当前 / Current |', '|---|---|']
    report.extend(f'| {key} | {value} |' for key, value in metrics.items())
    report.extend(['', '## 工作线 / Workstreams', ''])
    for key, stream in state.get('workstreams', {}).items():
        report.append(f"- {key}: {stream.get('status_zh', unknown)} / {stream.get('status_en', unknown)}")
    report.extend(['', '本日实际生产部署 / Actual production deployments today: UNKNOWN',
                   '', '已完成审核与周期证据见验收JSON；后续新改动仍需独立审核。待完成：真实生产遥测、新发布登记及持续并行。',
                   'Completed reviews and cycle evidence are in the validation JSON; future changes still require independent review. Pending: real production telemetry, new release registration and sustained parallel operation.',
                   '', '下一步：继续队列工程、审核各线提交，并通过受控入口查询发布状态。',
                   'Next: continue queued engineering, review stream commits, query releases through the controlled channel.',
                   '', '风险与未执行：未证明持续自主开发；本报告不授权生产DB或SMTP。',
                   'Risks and non-executed work: sustained autonomy is unproven; this report grants no production DB or SMTP access.', ''])
    path = root / 'autonomy' / 'BUSINESS_DAILY_REPORT.md'
    path.write_text('\n'.join(report), encoding='utf-8')
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init', 'cycle', 'dashboard'])
    parser.add_argument('--source', choices=['manual', 'codex_heartbeat'], default='manual')
    args = parser.parse_args()
    if args.action == 'init':
        init()
        print('QUEUE_READY / 队列已就绪')
    elif args.action == 'cycle':
        record = cycle(source=args.source)
        print(json.dumps({k: record[k] for k in ('cycle_id', 'status', 'task_id')}, ensure_ascii=False))
    else:
        dashboard()
        print('DASHBOARD_UPDATED / 日报已更新')


if __name__ == '__main__':
    main()
