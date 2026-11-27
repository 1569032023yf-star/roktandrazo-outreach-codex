"""Read durable Inventory receipts without treating an invocation as a search.

City attribution requires an unambiguous ID in the recorded stage trace.
Historic stage counters do not establish the number of newly found merchants.
"""
import json
import re
from pathlib import Path
from . import data


def _record(row):
    city_ids = set()
    places_entered = False
    trace = None
    try:
        trace = json.loads(row['current_step'] or '')
    except (ValueError, TypeError):
        pass
    if isinstance(trace, dict) and trace.get('schema') == 'rokt.inventory_stage_trace.v1' and isinstance(trace.get('events'), list):
        for event in trace['events']:
            if not isinstance(event, dict):
                continue
            city_id = event.get('city_id')
            if type(city_id) is int and city_id > 0:
                city_ids.add(city_id)
            if event.get('phase') == 'places' and event.get('outcome') == 'enter':
                places_entered = True
    city_id = next(iter(city_ids)) if len(city_ids) == 1 else None
    dry_run = row['dry_run']
    kind = '非模拟 Inventory 作业' if dry_run == 0 else '模拟作业' if dry_run == 1 else '运行性质未知'
    return {'run_id': row['run_id'], 'started_at': row['started_at'], 'finished_at': row['finished_at'],
            'status': row['status'], 'kind': kind, 'city_id': city_id,
            'city_evidence': '作业阶段回执中的城市 ID' if city_id else '未保存或存在冲突',
            'trace_city_conflict': len(city_ids) > 1,
            'places_stage_entered': places_entered, 'new_merchants': None,
            'new_merchants_reason': '阶段处理数量和库存总数不能证明本轮新增商家',
            'search_type': None, 'source': '正式库 job_runs'}


def _log_evidence(output, cities):
    """Accept only explicit same-run evidence; conflicting logs stay unknown."""
    root = Path(output)
    lookup = {}
    for city in cities:
        lookup.setdefault((city['city'].strip().casefold(), city['state']), []).append(city['id'])
    evidence = {}
    paths = sorted(set(root.glob('_canary_run_*.log')) | set(root.glob('inventory_run_*.log')) |
                   {p for p in root.glob('inventory_*.log') if re.fullmatch(r'inventory_\d{4}-\d{2}-\d{2}\.log', p.name)} |
                   {root / 'p24c_inventory_run.log'})
    for path in paths[:10000]:
        try:
            if path.stat().st_size > 2_000_000 or path.is_symlink():
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        if not re.search(r'BD Orchestrator[^\r\n]*stage=inventory[^\r\n]*dry_run=False', text):
            continue
        ids = set(re.findall(r'\brun_id:\s*(inventory:[A-Za-z0-9:_-]+)', text))
        names = set(re.findall(r'Active city:\s*([^,\r\n;]+),\s*([A-Z]{2})', text))
        retail = re.findall(r'Active retail city(?: \(state scope=([A-Z]{2})\))?:\s*([^,\r\n;]+),\s*([A-Z]{2})\s*\(no city switching\)', text)
        if any(scope and scope != state for scope, _, state in retail):
            continue
        names.update((name, state) for _, name, state in retail)
        if len(ids) != 1 or len(names) != 1:
            continue
        name, state = next(iter(names))
        matches = lookup.get((name.strip().casefold(), state), [])
        if len(matches) != 1:
            continue
        counts = {int(n) for n in re.findall(r'\bNEW_UNIQUE_PLACES=(\d+)', text)}
        item = {'city_id': matches[0], 'new_places': next(iter(counts)) if len(counts) == 1 else None,
                'source_file': path.name}
        evidence.setdefault(next(iter(ids)), []).append(item)
    return evidence


def inventory(path, page=1, city_id=None, output=None):
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError('页码无效')
    if city_id is not None and (type(city_id) is not int or not 1 <= city_id <= 9999):
        raise ValueError('城市编号无效')
    with data.readonly(path) as conn:
        rows = conn.execute("""SELECT run_id,started_at,finished_at,status,current_step,dry_run
            FROM job_runs WHERE stage='inventory' ORDER BY started_at DESC,run_id DESC""").fetchall()
        cities = [dict(row) for row in conn.execute('SELECT id,city,state FROM retail_city_queue')]
    records = [_record(row) for row in rows]
    sources = _log_evidence(output or Path(path).parent.parent / 'output', cities)
    for record in records:
        logs = sources.get(record['run_id'], []) if record['kind'] == '非模拟 Inventory 作业' else []
        if record['trace_city_conflict']:
            record['city_evidence'] = '作业阶段回执包含多个城市，待核对'
            continue
        ids = {item['city_id'] for item in logs}
        if record['city_id'] is not None:
            ids.add(record['city_id'])
        if len(ids) > 1:
            record['city_id'] = None
            record['city_evidence'] = '作业回执与日志城市冲突，待核对'
        elif len(ids) == 1 and logs:
            if record['city_id'] is None:
                record['city_id'] = next(iter(ids))
                record['city_evidence'] = '相同运行编号的原始日志及唯一城市匹配'
            places = {item['new_places'] for item in logs}
            record['new_places'] = next(iter(places)) if len(places) == 1 else None
            record['log_sources'] = sorted(item['source_file'] for item in logs)
    if city_id is not None:
        records = [r for r in records if r['city_id'] == city_id]
    size = 50
    return {'items': records[(page - 1) * size:page * size], 'total': len(records),
            'page': page, 'page_size': size, 'observed_at': data.now(),
            'source': '正式库 job_runs（只读）',
            'scope': '只读正式库 Inventory 作业，并关联指定 output 目录中可识别的原始日志；其他历史来源尚未全部接入。Inventory 作业次数并非实际城市搜索次数；缺少城市回执的旧记录未归属。'}


def city_request_audit(path, city_id, page=1):
    """Show persisted source-level audit rows without inventing run attribution."""
    if type(city_id) is not int or not 1 <= city_id <= 9999:
        raise ValueError('城市编号无效')
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError('页码无效')
    size = 50
    with data.readonly(path) as conn:
        total = conn.execute('SELECT COUNT(*) FROM provider_request_audit WHERE active_city_id=?', (city_id,)).fetchone()[0]
        rows = conn.execute('''SELECT id,requested_at,provider,query_family,source_query,status,
            request_count,result_count FROM provider_request_audit WHERE active_city_id=?
            ORDER BY requested_at DESC,id DESC LIMIT ? OFFSET ?''',
            (city_id, size, (page - 1) * size)).fetchall()
    return {'items': [dict(row) for row in rows], 'total': total, 'page': page,
            'page_size': size, 'city_id': city_id, 'observed_at': data.now(),
            'source': '正式库 provider_request_audit（只读）',
            'scope': '来源审计行不是城市搜索次数；部分行记录配置阻断或失败。作业编号、运行性质和本轮新增商家无法从该表可靠确认。结果数为原始结果而非独立商家。'}


def report_snapshots(output):
    """Read known historic report snapshots, never treat files as distinct runs."""
    root = Path(output)
    if not root.is_dir():
        return {'available': False, 'items': [], 'unreadable': None, 'observed_at': data.now()}
    items, unreadable = [], 0
    for path in sorted(root.glob('inventory_final_report_*.json'))[:10000]:
        if not re.fullmatch(r'inventory_final_report_\d{8}_\d{4}\.json', path.name):
            continue
        try:
            if path.is_symlink() or path.stat().st_size > 2_000_000:
                raise ValueError('unsupported file')
            obj = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(obj, dict):
                raise ValueError('not a report')
            def text_field(key):
                value = obj.get(key)
                return value if isinstance(value, str) and len(value) <= 200 else None
            def count_field(key):
                value = obj.get(key)
                return value if type(value) is int and 0 <= value <= 2**63-1 else None
            items.append({'filename': path.name, 'updated_at': text_field('updated_at'),
                          'status': text_field('status'), 'candidates_discovered': count_field('candidates_discovered'),
                          'candidates_verified': count_field('candidates_verified'), 'a0_added': count_field('a0_added'),
                          'run_id': None, 'city': None, 'run_kind': '未知'})
        except (OSError, ValueError, TypeError):
            unreadable += 1
    return {'available': True, 'items': items, 'unreadable': unreadable, 'observed_at': data.now(),
            'scope': '仅展示指定历史报告快照；文件可能属于同一次运行，不计为搜索次数，不推断城市或运行性质。'}
