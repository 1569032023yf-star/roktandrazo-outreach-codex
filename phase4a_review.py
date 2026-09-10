"""Compare local deployment snapshots / 比较本地部署快照。"""
import json
import sys
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

def main():
    root=Path(sys.argv[1]).resolve()
    assert root.is_relative_to(Path(__file__).resolve().parent/'_audit_quarantine'/'phase4a')
    before=json.loads((root/'before.json').read_text(encoding='utf-8'))
    after=json.loads((root/'after.json').read_text(encoding='utf-8'))
    old={r['id']:r for r in before['leads']}
    oldstage={r['id']:r for r in before['staging']}
    changed=[r for r in after['staging'] if oldstage.get(r['id'])!=r]
    promoted=[r for r in after['leads'] if r.get('email') and r.get('email')!=old.get(r['id'],{}).get('email')]
    failures=[]
    details=[]
    for row in changed:
        ev=json.loads(row.get('raw_payload_json') or '{}').get('official_email_evidence') or {}
        details.append({k:row.get(k) for k in ('id','business_name','city','state','website','linked_lead_id','validation_status') } | {'evidence':ev})
    for lead in promoted:
        records=[d for d in details if d['linked_lead_id']==lead['id'] and d['evidence'].get('email')==lead['email']]
        if not records:
            failures.append({'lead_id':lead['id'],'reason':'NO_FULL_STAGING_EVIDENCE'})
            continue
        ev=records[0]['evidence']
        same=lambda u:urlsplit(u).netloc.lower().removeprefix('www.')
        if not (ev.get('http_success') is True and ev.get('tls_success') is True and 200<=int(ev.get('http_status',0))<300 and
                lead['email'] in ev.get('visible_text_excerpt','') and ev.get('content_hash') and
                ev.get('email_source_type')=='official_page_visible' and same(ev.get('final_url',''))==same(lead.get('official_website',''))):
            failures.append({'lead_id':lead['id'],'reason':'INVALID_EVIDENCE'})
    def dup(rows):
        keys=[(r.get('store_name','').strip().lower(),r.get('city','').lower(),r.get('state','').lower(),r.get('formatted_address','')) for r in rows]
        return len(keys)-len(set(keys))
    report={'before':before['metrics'],'after':after['metrics'],'delta':{k:None if after['metrics'][k] is None else after['metrics'][k]-v for k,v in before['metrics'].items()},
        'schema_unchanged':before['schema']==after['schema'],'changed_staging_count':len(changed),'promoted_email_count':len(promoted),
        'new_duplicate_lead_keys':dup(after['leads'])-dup(before['leads']),'evidence_failures':failures,'merchant_review':details,
        'latest_jobs':after['job_runs'][:2]}
    prod=Path(r'C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach\data\bd_leads.db')
    with sqlite3.connect((root/'database/bd_leads.db').as_uri()+'?mode=ro',uri=True) as bc, sqlite3.connect(prod.as_uri()+'?mode=ro',uri=True) as ac:
        tables={r[0] for r in bc.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        protected=[n for n in tables if n in {'send_log','bounce_log','suppression_list','final_send_plan'} or n.startswith('send_authorization')]
        report['protected_table_counts']={n:{'before':bc.execute('SELECT count(*) FROM '+n).fetchone()[0],'after':ac.execute('SELECT count(*) FROM '+n).fetchone()[0]} for n in protected}
    (root/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':
    main()
