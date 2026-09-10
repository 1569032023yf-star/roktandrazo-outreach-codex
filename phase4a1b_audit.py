"""Read-only linked backlog audit / 只读已关联积压审计。"""
import collections
import json
import sqlite3
from pathlib import Path


def audit(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("""SELECT s.*, l.review_reason_code,
        l.review_reason_detail FROM lead_discovery_results s JOIN leads l
        ON l.id=s.linked_lead_id WHERE trim(coalesce(l.email,''))=''""")]
    result = {'linked_rows': len(rows)}
    for key in ('validation_status', 'review_reason_code', 'review_reason_detail',
                'official_match', 'rejection_reason'):
        result[key] = dict(sorted(collections.Counter(str(r[key]) for r in rows).items()))
    for key in ('website', 'evidence_url', 'evidence_snippet'):
        result[key] = dict(collections.Counter('present' if str(r[key] or '').strip() else 'missing' for r in rows))
    result['full_evidence_present'] = sum(bool(json.loads(r['raw_payload_json'] or '{}').get('official_email_evidence')) for r in rows)
    result['full_evidence_missing'] = len(rows) - result['full_evidence_present']
    result['active_city_id'] = dict(collections.Counter(str(r['active_city_id']) for r in rows))
    conn.close()
    return result


if __name__ == '__main__':
    import sys
    result = audit(sys.argv[1])
    root = Path(__file__).resolve().parent / 'handoff' / 'phases'
    text = json.dumps(result, ensure_ascii=False, indent=2)
    (root / 'PHASE4A1B_ROUTING_AUDIT.json').write_text(text + '\n', encoding='utf-8')
    (root / 'PHASE4A1B_ROUTING_AUDIT.md').write_text(
        '# 已关联积压路由审计 / Linked backlog routing audit\n\n'
        '实施前只读副本分类；明细值逐项精确计数。 / Pre-implementation read-only snapshot classification; exact counts for every detail value.\n\n'
        '注意：非空旧证据摘录不等于完整官方邮箱证据。 / Nonempty legacy snippets are not complete official email evidence.\n\n'
        '```json\n' + text + '\n```\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'review_reason_detail'}, ensure_ascii=False))
