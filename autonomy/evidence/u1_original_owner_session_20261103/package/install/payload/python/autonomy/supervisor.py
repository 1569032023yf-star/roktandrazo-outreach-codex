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
    from autonomy.lock_recovery import exclusive_lock, mark_tree
    from autonomy.process_job import run_tree
    from autonomy.storage_preflight import check_storage
except ModuleNotFoundError:
    from lock_recovery import exclusive_lock, mark_tree
    from process_job import run_tree
    from storage_preflight import check_storage

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
        handle = os.fdopen(fd, 'w', encoding='utf-8')
        try:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException as error:
            # Capture the write failure before close can flush and fail again.
            try:
                handle.close()
            except BaseException:
                error.add_note('FILE_CLOSE_FAILED')
            raise
        else:
            # With no write failure, close itself is the primary failure.
            handle.close()
        os.replace(tmp, path)
    except BaseException as error:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            error.add_note('TEMP_CLEANUP_FAILED')
        raise
    else:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        handle = os.fdopen(fd, 'w', encoding='utf-8')
        try:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException as error:
            # Capture the write failure before close can flush and fail again.
            try:
                handle.close()
            except BaseException:
                error.add_note('FILE_CLOSE_FAILED')
            raise
        else:
            # With no write failure, close itself is the primary failure.
            handle.close()
        os.replace(tmp, path)
    except BaseException as error:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            error.add_note('TEMP_CLEANUP_FAILED')
        raise
    else:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def exclusive(runtime):
    """Instance-token lock, serialized against explicit recovery / 实例令牌互斥锁。"""
    with exclusive_lock(runtime):
        yield


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
            path = runtime / 'cycles' / (record['cycle_id'] + '.json')
            try:
                existing = read(path)
            except (ValueError, UnicodeError):
                existing = None
            if existing != record:
                atomic_json(path, record)


def task_prompt(task):
    # Queue data never becomes executable commands or arbitrary agent instructions.
    if task['id'] == 'D-output-cleanup-repair' and task['role'] == 'developer':
        return ('执行有界开发，先读AGENTS和docs/AUTONOMY_RELIABILITY_CLOSURE_REVIEW.md。'
                '仅补R3/R4：输出读取线程及无线程关闭失败必须纳入cleanup错误，保留主异常；'
                'supervisor保留白名单化OUTPUT_LIMIT和CLEANUP_UNVERIFIED证据而不输出异常消息。'
                '允许最小修改autonomy/process_job.py、test_process_job.py、supervisor.py、test_supervisor.py'
                '及新增双语docs/AUTONOMY_OUTPUT_CLEANUP_REPAIR.md。候选启动器原始副本及hash在'
                'autonomy/runtime/preserved_runner_20261021，保留既有功能，不覆盖整个文件。'
                '补合成线程close故障及主异常组合测试；正常Python若被拒绝就报告，禁止改安全策略。'
                '不改lock_recovery.py、不自动删锁、不联网或启动真实代理、不触生产DB/SMTP。'
                '10分钟内退出、不自行提交，最终JSON summary_zh/summary_en/findings。')
    if task['id'] == 'D-output-cleanup-review' and task['role'] == 'reviewer':
        return ('独立只读审核process_job.py/test_process_job.py及supervisor.py最新输出清理补修；'
                '依据docs/AUTONOMY_RELIABILITY_CLOSURE_REVIEW.md核查R3/R4及输出限额、异常清理。'
                '可以运行离线合成测试，不联网、不改文件、不运行真实代理或生产DB/SMTP。'
                '不能测试时如实说明，最终JSON summary_zh/summary_en/findings。')
    if task['id'] in {'D-unknown-outcome-quarantine', 'D-unknown-outcome-followup', 'D-write-close-preservation'} and task['role'] == 'developer':
        return ('执行一项有界开发：先读AGENTS.md及docs/AUTONOMY_STORAGE_FAILURE_AUDIT.md。'
                '如存在docs/AUTONOMY_FOLLOWUP_REVIEW.md，优先补修atomic_json写入失败叠加文件close失败：在关闭前保存原异常，关闭失败仅附注，补纯内存组合故障及close单独失败测试；不关闭其余存储发现。'
                '如存在docs/AUTONOMY_UNKNOWN_OUTCOME_REVIEW.md，先修其两项：developer completed恢复必须去重排独立审核；exclusive锁删除失败须保留正在传播的主异常及附注，并补组合故障测试。'
                '仅修改autonomy/supervisor.py、autonomy/test_supervisor.py，新增或更新双语'
                'docs/AUTONOMY_UNKNOWN_OUTCOME_RECOVERY.md。优先修复审查前两项：'
                '中断running、代理超时/输出不完整/执行异常及执行后完成提交失败，结果未知必须隔离，'
                '不得自动重执行；仅经显式只读成果核对才允许恢复，不能按attempts或needs_reassessment放行。'
                '区分queue未提交与queue成功receipt失败，queue仍权威，只补缺失或不一致receipt；'
                '保留原始写入异常，清理临时文件失败不得覆盖它。以合成runner计数及注入dump/flush/'
                'fsync/replace/receipt故障验证旧JSON完整和未知任务调用次数仍为1。更新旧自动重跑测试'
                '以匹配新保守契约，不降低断言。保持真实触发证据规则、锁、生产隔离和固定角色。'
                '不修改process_job.py，不执行真实代理/联网/采集/生产DB/SMTP，不读取凭据，'
                '不删除用户文件，不自行提交。10分钟内完成可验证改动或如实报告未完成。'
                '最终仅JSON summary_zh、summary_en、findings数组。')
    if task['id'] in {'D-unknown-outcome-review', 'D-unknown-outcome-followup-review', 'D-write-close-review'} and task['role'] == 'reviewer':
        return ('独立只读审核autonomy/supervisor.py、test_supervisor.py及'
                'docs/AUTONOMY_UNKNOWN_OUTCOME_RECOVERY.md，对照存储失败专项审核报告。'
                '重点验证未知结果隔离、禁止自动重执行、queue权威与receipt恢复、主异常保留、'
                '测试真实覆盖且未放宽断言。不得改文件、联网、启动代理或访问生产DB/SMTP/凭据。'
                '仅纯内存验证；不能执行的测试如实列明。最终仅JSON summary_zh、summary_en、'
                'findings数组，每项severity/file/detail_zh/detail_en。')
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
    mark_tree('unverified')
    try:
        result = run_tree(args, timeout=timeout, cwd=root)
    except Exception as error:
        verified = getattr(error, 'cleanup_verified', False) is True
        lock_error_type = None
        if verified:
            try:
                mark_tree('verified_closed')
            except Exception as lock_error:
                # Preserve the process failure even if its lock receipt cannot persist.
                lock_error_type = type(lock_error).__name__
        reason = ('AGENT_TIMEOUT' if isinstance(error, subprocess.TimeoutExpired)
                  else getattr(error, 'reason', 'AGENT_PROCESS_ERROR'))
        # Serialize only fixed classifications, never prompts, output or exception text.
        allowed = {'AGENT_TIMEOUT', 'OUTPUT_LIMIT', 'PROCESS_TREE_CLEANUP_UNVERIFIED'}
        if reason not in allowed:
            reason = 'AGENT_PROCESS_ERROR'
        errors = tuple(getattr(error, 'cleanup_errors', ()))
        return {'ok': False, 'reason': reason, 'result': 'UNKNOWN',
                'cleanup_verified': verified,
                'cleanup_errors': [str(x) for x in errors if str(x).isidentifier()],
                'error_type': type(error).__name__,
                'lock_state_update_failed': lock_error_type is not None,
                'lock_state_update_error_type': lock_error_type}
    mark_tree('verified_closed')
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


def enqueue_independent_review(state, task):
    reviews = {'D-sanitized-telemetry-adapter': ('D', 'D-telemetry-independent-review'),
               'D-unknown-outcome-quarantine': ('D', 'D-unknown-outcome-review'),
               'D-unknown-outcome-followup': ('D', 'D-unknown-outcome-followup-review'),
               'D-write-close-preservation': ('D', 'D-write-close-review'),
               'D-output-cleanup-repair': ('D', 'D-output-cleanup-review'),
               'B-brand-package-integration': ('B', 'B-brand-integration-review')}
    if task['role'] == 'developer' and task['id'] in reviews:
        workstream, review_id = reviews[task['id']]
        if not any(t['id'] == review_id for t in state['tasks']):
            state['tasks'].append({'id': review_id, 'workstream': workstream,
                'status': 'queued', 'attempts': 0, 'role': 'reviewer', 'blocked_cycles': 0})


def cycle(runtime=RUNTIME, root=ROOT, source='manual', runner=run_agent):
    if source not in {'manual', 'codex_heartbeat'}:
        raise ValueError('INVALID_SOURCE')
    with exclusive(runtime):
        _init_locked(runtime)
        state = read(runtime / 'queue.json')
        reconcile(runtime, state)
        # A prior worker may have died after persisting a running lease.
        for task in state['tasks']:
            prior = next((r for r in state['cycles']
                          if r['cycle_id'] == task.get('lease_cycle_id')), None)
            legacy_unknown = (task['status'] in {'queued', 'blocked'} and prior
                              and prior['status'] in {'failed', 'interrupted', 'unknown'}
                              and task.get('reconciliation', {}).get('lease_cycle_id')
                              != task.get('lease_cycle_id'))
            if task['status'] == 'running' or legacy_unknown:
                task.update(status='unknown', outcome_unknown=True,
                            recovery_reason='PRIOR_CYCLE_INTERRUPTED',
                            blocked_cycles=task.get('blocked_cycles', 0) + 1)
                task['needs_reassessment'] = True
                for prior in state['cycles']:
                    if prior['cycle_id'] == task.get('lease_cycle_id') and prior['status'] == 'running':
                        prior.update(status='unknown', finished_at=now(),
                                     outcome={'ok': False, 'reason': 'PRIOR_CYCLE_INTERRUPTED',
                                              'result': 'UNKNOWN'})
        atomic_json(runtime / 'queue.json', state)
        reconcile(runtime, state)
        eligible = [t for t in state['tasks'] if t['status'] == 'queued'
                    and not t.get('outcome_unknown') and t['attempts'] < 3]
        record = {'cycle_id': str(uuid.uuid4()), 'source': source, 'started_at': now(),
                  'status': 'idle', 'task_id': None, 'human_trigger_excluded': source == 'manual'}
        state['cycles'].append(record)
        if eligible:
            task = eligible[0]
            storage = check_storage(runtime, root)
            record['storage_preflight'] = storage
            if not storage['allow_start']:
                task['blocked_cycles'] = task.get('blocked_cycles', 0) + 1
                task['needs_reassessment'] = task['blocked_cycles'] >= 2
                record.update(status='blocked_preflight', task_id=task['id'],
                              outcome={'ok': False, 'reason': 'STORAGE_PREFLIGHT_BLOCKED',
                                       'execution_started': False})
                eligible = []
        if eligible:
            task = eligible[0]
            task.update(status='running', attempts=task['attempts'] + 1,
                        lease_cycle_id=record['cycle_id'])
            record.update(status='running', task_id=task['id'])
            atomic_json(runtime / 'queue.json', state)
            try:
                outcome = runner(task, root)
                if not isinstance(outcome, dict) or type(outcome.get('ok')) is not bool:
                    outcome = {'ok': False, 'reason': 'RUNNER_INCOMPLETE'}
            except Exception as error:
                # Never serialize exception messages, prompts or environment secrets.
                outcome = {'ok': False, 'reason': 'RUNNER_EXCEPTION', 'type': type(error).__name__}
            task['status'] = ('needs_review' if task['role'] == 'developer' else 'completed') if outcome['ok'] else 'unknown'
            if outcome['ok']:
                enqueue_independent_review(state, task)
            task['blocked_cycles'] = 0 if outcome['ok'] else task.get('blocked_cycles', 0) + 1
            task['needs_reassessment'] = not outcome['ok']
            task['outcome_unknown'] = not outcome['ok']
            if not outcome['ok']:
                outcome = dict(outcome, result='UNKNOWN')
            record.update(status='completed' if outcome['ok'] else 'unknown', outcome=outcome)
        record['finished_at'] = now()
        try:
            atomic_json(runtime / 'queue.json', state)
        except Exception as error:
            # The durable running lease is quarantined on restart, never retried.
            error.add_note('QUEUE_COMMIT_FAILED_OUTCOME_UNKNOWN')
            raise
        try:
            atomic_json(runtime / 'cycles' / (record['cycle_id'] + '.json'), record)
        except Exception as error:
            error.add_note('QUEUE_COMMITTED_RECEIPT_PENDING')
            raise
        return record


def recover_unknown(runtime, task_id, readonly_check):
    """Explicit read-only artifact reconciliation; never called by cycle().

    The caller supplies a trusted checker, not a runner or queue-supplied code.
    Evidence must prove completion or non-execution; uncertainty stays isolated.
    """
    with exclusive(runtime):
        state = read(runtime / 'queue.json')
        task = next(t for t in state['tasks'] if t['id'] == task_id)
        if task['status'] != 'unknown' or not task.get('outcome_unknown'):
            raise ValueError('TASK_NOT_QUARANTINED')
        result = readonly_check(json.loads(json.dumps(task)))
        if (not isinstance(result, dict) or result.get('read_only') is not True
                or result.get('resolution') not in {'completed', 'not_executed'}
                or not isinstance(result.get('evidence'), str)
                or not result['evidence'].strip()):
            raise ValueError('READONLY_RECONCILIATION_REQUIRED')
        task['reconciliation'] = dict(result, checked_at=now(),
                                      lease_cycle_id=task.get('lease_cycle_id'))
        task['status'] = ('needs_review' if task['role'] == 'developer' else 'completed') if result['resolution'] == 'completed' else 'queued'
        if result['resolution'] == 'completed':
            enqueue_independent_review(state, task)
        task.update(outcome_unknown=False, needs_reassessment=False)
        atomic_json(runtime / 'queue.json', state)
        return task


def two_unattended_cycles(records):
    """Conservative: idle, manual, failed or closely spaced runs never qualify.

    Source labels alone are not authenticity proof. The app's two trigger receipts
    must be independently matched before promoting the validation flag.
    """
    return False


def _preserve_newer_observation(root, observed):
    saved = read(root / 'autonomy/runtime/telemetry/latest_business_observation.json', {})
    previous = saved.get('observed_at')
    if previous is None:
        return False
    try:
        previous = datetime.fromisoformat(previous)
        if previous.tzinfo is None:
            raise ValueError()
        if observed == 'UNKNOWN':
            age = (datetime.now(timezone.utc) - previous).total_seconds()
            publication = read(root / 'autonomy/runtime/telemetry/report_publication.json', {})
            report = root / 'autonomy/BUSINESS_DAILY_REPORT.md'
            return (0 <= age <= 3600 and publication.get('observed_at') == saved.get('observed_at')
                    and report.is_file() and publication.get('report_sha256')
                    == hashlib.sha256(report.read_bytes()).hexdigest())
        incoming = datetime.fromisoformat(observed)
        if incoming.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('REPORT_OBSERVATION_STATE_INVALID') from None
    if incoming < previous:
        raise ValueError('OLDER_OBSERVATION_REJECTED')
    return False


def persist_business_observation(root, *, bridge_receipt, observation):
    """Serialize shared local reports; HTTP and immutable receipts stay outside.

    共享报告使用同一互斥；HTTP与不可变回执在锁外。
    """
    root = Path(root)
    with exclusive(root / 'autonomy/runtime'):
        _preserve_newer_observation(root, observation['observed_at'])
        state = read(root / 'autonomy/WORKSTREAM_STATUS.json', {})
        state['production_observation'] = observation
        # Queue/observation receipt remains authoritative if a later report fails.
        atomic_json(root / 'autonomy/runtime/telemetry/latest_business_observation.json', observation)
        atomic_json(root / 'autonomy/WORKSTREAM_STATUS.json', state)
        return _dashboard_locked(root, bridge_receipt=bridge_receipt)


def dashboard(root=ROOT, *, bridge_receipt=None):
    root = Path(root)
    if bridge_receipt is not None:
        try:
            from autonomy.telemetry import consume_bridge_receipt, InvalidSnapshot
        except ModuleNotFoundError:
            from telemetry import consume_bridge_receipt, InvalidSnapshot
        try:
            observation = consume_bridge_receipt(bridge_receipt,
                approved_channel='rokt-deploy-channel')
        except InvalidSnapshot:
            pass
        else:
            return persist_business_observation(root, bridge_receipt=bridge_receipt,
                observation=observation)
    with exclusive(root / 'autonomy/runtime'):
        return _dashboard_locked(root, bridge_receipt=bridge_receipt)


def _dashboard_locked(root, *, bridge_receipt=None):
    """Preserve historical reports; render a fresh authenticated aggregate section.

    保留历史日报，固定回执来源由受控采集调用方负责认证；缺证不补零。
    """
    try:
        from autonomy.telemetry import consume_bridge_receipt, InvalidSnapshot
    except ModuleNotFoundError:
        from telemetry import consume_bridge_receipt, InvalidSnapshot
    metrics = {key: 'UNKNOWN' for key in (
        'NEW_VERIFIED_ORGANIZATIONS_24H', 'NEW_FIRST_PARTY_EMAILS_24H',
        'SAFE_TOTAL_LATEST', 'SAFE_NET_GROWTH_7D', 'ACTIVE_CITY',
        'HISTORICAL_LEADS', 'HISTORICAL_LEADS_WITH_EMAIL',
        'PROVIDER_REQUESTS_24H', 'SENDS_TODAY', 'SMTP_OBSERVED',
        'LAST_INVENTORY_RUN', 'GLOBAL_INVENTORY_UNIQUENESS')}
    observed = 'UNKNOWN'
    source_note = 'UNKNOWN / NOT_VALIDATED'
    if bridge_receipt is not None:
        try:
            live = consume_bridge_receipt(bridge_receipt,
                approved_channel='rokt-deploy-channel')
        except InvalidSnapshot:
            live = None
        if live:
            observed = live['observed_at']
            source_note = 'authenticated rokt-deploy-channel v2 telemetry; freshness <= 1h'
            metrics.update(HISTORICAL_LEADS=live['historical_totals']['leads_total'],
                HISTORICAL_LEADS_WITH_EMAIL=live['historical_totals']['leads_with_email'],
                PROVIDER_REQUESTS_24H=live['rolling_24h']['provider_requests'],
                SENDS_TODAY=live['safety']['sent_today'],
                SMTP_OBSERVED=live['safety']['smtp_observed'])
            active = [x['city'] for x in live['active_cities']
                      if x['status'].lower() == 'active']
            metrics['ACTIVE_CITY'] = ', '.join(active) if active else 'UNKNOWN'
            last = live['last_inventory_run']
            metrics['LAST_INVENTORY_RUN'] = last['run_id'] if isinstance(last, dict) else 'UNKNOWN'
    if _preserve_newer_observation(root, observed):
        return metrics
    state = read(root / 'autonomy' / 'WORKSTREAM_STATUS.json', {})
    lines = ['## 自动业务观察 / Automated business observation', '',
             f'观测时间 / Observed at: {observed}',
             f'来源 / Source: {source_note}', '',
             '历史累计、最近运行actual和当前SAFE不是同一指标；缺少阶段/资格合同的字段保持UNKNOWN。',
             'Historical totals, the latest run actual and current SAFE are distinct. Missing stage/eligibility contracts remain UNKNOWN.', '',
             '| 指标 / Metric | 结果 / Result |', '|---|---|']
    lines.extend(f'| {key} | {value} |' for key, value in metrics.items())
    lines.extend(['', '## 工作线快照 / Workstream snapshot', ''])
    for key, stream in state.get('workstreams', {}).items():
        lines.append(f"- {key}: {stream.get('status_zh', 'UNKNOWN')} / {stream.get('status_en', 'UNKNOWN')}")
    lines.extend(['', '未执行与风险：未据库存56确认SAFE；未确认完整阶段、全局调度唯一性或持续无人值守。',
                  'Not executed / risks: inventory 56 does not confirm SAFE; full stage telemetry, global scheduler uniqueness and sustained unattended operation remain unverified.',
                  '下一步：消费既有运维受限补证；无新数据时推进其他已授权工程。',
                  'Next: consume the existing bounded operations handoff; advance other authorized engineering when data is unavailable.',
                  '敏感检查：仅固定脱敏聚合，无凭据及客户明细。',
                  'Sensitive-data check: fixed sanitized aggregates only; no credentials or customer records.', ''])
    path = root / 'autonomy' / 'BUSINESS_DAILY_REPORT.md'
    original = path.read_text(encoding='utf-8-sig') if path.exists() else '# ROKT&RAZO 业务日报 / Business Daily Report\n'
    begin, end = '<!-- BD_LIVE_OBSERVATION_BEGIN -->', '<!-- BD_LIVE_OBSERVATION_END -->'
    section = begin + '\n' + '\n'.join(lines) + '\n' + end
    if begin in original and end in original and original.index(begin) < original.index(end):
        left, right = original.index(begin), original.index(end) + len(end)
        original = original[:left] + section + original[right:]
    else:
        original += '\n\n' + section + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(path, original)
    atomic_json(root / 'autonomy/runtime/telemetry/report_publication.json', {
        'observed_at': observed,
        'report_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
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
