"""Pure evidence projection. Missing observations are never converted to zero."""
import json
from datetime import datetime, timezone

PHASES = {'inventory': '整轮作业', 'state': '确定搜索州', 'city': '选择城市',
          'places': '寻找商家', 'website': '查找官网', 'postprocess': '核实候选',
          'linked': '处理关联待办', 'completion': '检查城市能否结束'}

# Rule explanation is valid only for the production source inspected on 2026-11-26.
DIAGNOSTIC_HASHES = {
    'retail_city_queue.py': '27d60fa77644f15b786bfc61390d3671d4a3ee50cc8ae6e9e0fa42b19e820146',
    'discovery/discovery_service.py': 'abc2f682cbff4a8b6781997bc2a08ac00f5e41289d67ce02b1c7afa519ad6770',
    'discovery/website_resolver.py': '8945d43975e4f5750baa956adae0c8f3de5b6b9374741be4217b1b5289844f8f',
}


def diagnostic_rules_match(city, health):
    rules = city.get('ruleset') or {}
    hashes = health.get('production_code_sha256') or {}
    return (all(hashes.get(k) == v for k, v in DIAGNOSTIC_HASHES.items())
            and (rules.get('module_fingerprint') or {}).get('sha256') == DIAGNOSTIC_HASHES['retail_city_queue.py']
            and (rules.get('discovery_fingerprint') or {}).get('sha256') == DIAGNOSTIC_HASHES['discovery/discovery_service.py'])


def trace(run):
    try:
        raw = run.get('current_step')
        raw = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(raw, dict) or raw.get('schema') != 'rokt.inventory_stage_trace.v1':
            return []
        events = raw.get('events')
        if not isinstance(events, list):
            return []
        return [{k: e.get(k) for k in ('seq', 'phase', 'outcome', 'at', 'city_id', 'count')}
                for e in events if isinstance(e, dict) and e.get('phase') in PHASES]
    except (ValueError, TypeError):
        return []


def runs(runtime):
    result = []
    for row in runtime.get('runs', []):
        if row.get('stage') != 'inventory':
            continue
        events = trace(row)
        counts = {e['phase']: e['count'] for e in events if e['outcome'] == 'complete'
                  and type(e['count']) is int}
        cities = {e['city_id'] for e in events if type(e['city_id']) is int}
        result.append({k: row.get(k) for k in ('run_id', 'status', 'stop_reason', 'actual',
            'process_started_at', 'process_finished_at', 'error_class')} | {
            'events': events, 'counts': counts, 'city_id': next(iter(cities)) if len(cities) == 1 else None,
            'new_organizations': None})
    return result


def fresh(envelope, current=None):
    try:
        at = datetime.fromisoformat(envelope['observed_at'])
        if at.tzinfo is None:
            return False
        age = ((current or datetime.now(timezone.utc)) - at).total_seconds()
        return not envelope.get('error') and 0 <= age <= 300
    except (KeyError, ValueError, TypeError):
        return False


def explain(city, latest=None):
    checks = city.get('completion_checks') or {}
    record = city.get('city') or {}
    query = city.get('query_families') or {}
    blocking = city.get('blocking_attribution') or {}
    issues = []
    exhausted = checks.get('all_query_families') is True and checks.get('pagination_complete') is True
    if city.get('completion_checks_all_met') is True and record.get('completed_at'):
        search = '本轮已结束（生产记录）'
    elif exhausted:
        search = '地图查询已结束 · 城市尚未关闭'
    elif query.get('total') is None:
        search = '搜索进度未知'
    elif record.get('city_status', '').lower() in {'pending', 'queued'}:
        search = '待搜索'
    else:
        search = '搜索尚未完成'
    if record.get('web_directory_status') == 'web_directory_provider_not_configured':
        issues.append({'title': '网页 / 目录搜索来源未配置', 'detail': '现有规则接受未配置原因；不能据此宣称全城市商家已经找完。',
                       'next': '在下一阶段确认本轮必需来源和搜索范围。', 'refs': []})
    for key, title, detail in [
        ('linked_backlog_retry_refs', '关联商家待办仍阻止城市关闭', '完成检查仍认为有可恢复记录；若本轮处理数为 0，需要核对执行器为何没有选中。'),
        ('staged_pending_refs', '有候选尚未处理', '候选暂存流程尚未结束。'),
        ('retryable_manual_review_refs', '有可重试的审核记录', '当前完成规则仍把这些条目计为待处理。'),
        ('auto_recovery_deferred_refs', '部分条目已延期处理', '这些是自动恢复延期记录，不应与硬阻塞直接相加。')]:
        count = blocking.get(key + '_count')
        if type(count) is int and count > 0:
            issues.append({'title': f'{title} · {count} 条', 'detail': detail,
                           'next': '点击记录编号查看商家与现存原因；本看板不触发重试。', 'refs': blocking.get(key, [])})
    states = [city.get('active_discovery_state'), city.get('active_city_state_config')]
    if all(states) and states[0] != states[1]:
        issues.append({'title': '搜索州配置存在分歧', 'detail': f'发现服务为 {states[0]}，旧城市配置为 {states[1]}。',
                       'next': '正式接入计划控制前，统一实际执行入口的地区规则。', 'refs': []})
    if latest and latest.get('city_id') == record.get('city_id') and latest.get('counts', {}).get('places') == 0:
        reason = ('本轮商家搜索阶段计数为 0；当前地图查询已耗尽。按现有实现，没有待执行查询时会直接返回。'
                  '这是当前查询状态与运行计数的解释，不是逐请求证明。' if exhausted else
                  '本轮商家搜索阶段计数为 0；仅凭计数无法区分没有请求、空结果或过滤，需要请求证据。')
        issues.insert(0, {'title': '为什么显示 0？', 'detail': reason,
                          'next': '查看查询明细、请求审计及关联待办；库存数量不代表本轮新增。', 'refs': []})
    return {'search_label': search, 'qualification_label':
            ('关闭检查已通过 · 商家仍需按各自资格判断' if city.get('completion_checks_all_met') is True
             else '仍有待办或完成证据不足'), 'issues': issues}
