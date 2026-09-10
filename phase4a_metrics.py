"""Read-only live Inventory metrics / 只读生产 Inventory 指标。"""
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
PROD=Path(r'C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach')
sys.dont_write_bytecode=True
sys.path.insert(0,str(PROD))

def guard(event,args):
    if event.startswith(('smtplib.','imaplib.')):
        raise RuntimeError('MAIL_FORBIDDEN')
    if event=='socket.connect' and isinstance(args[1],tuple) and args[1][1] in (25,465,587,143,993,110,995):
        raise RuntimeError('MAIL_FORBIDDEN')

sys.addaudithook(guard)

def main():
    dest=Path(sys.argv[1]).resolve()
    assert dest.is_relative_to(ROOT/'_audit_quarantine'/'phase4a')
    c=sqlite3.connect((PROD/'data/bd_leads.db').as_uri()+'?mode=ro',uri=True)
    c.row_factory=sqlite3.Row
    leads=[dict(r) for r in c.execute('SELECT * FROM leads')]
    staging=[dict(r) for r in c.execute('SELECT * FROM lead_discovery_results')]
    fields={'requested_url','final_url','http_status','http_success','tls_success','fetched_at','visible_text_excerpt','content_hash','email','email_source_type'}
    full=[]
    for row in staging:
        ev=json.loads(row.get('raw_payload_json') or '{}').get('official_email_evidence') or {}
        if fields<=ev.keys() and ev.get('email') and ev['email'] in ev['visible_text_excerpt'] and ev['http_success'] is True and ev['tls_success'] is True:
            full.append(row['id'])
    offline='--offline' in sys.argv
    if offline:
        selected=[]
    else:
        import env_loader
        from campaign_eligible_v2 import select_candidates_for_plan_v2
        selected=select_candidates_for_plan_v2(c,1000000)
    orgs={r['organization_key'] for r in selected if r.get('organization_key')}
    metrics={'TOTAL_LEADS':len(leads),'WEBSITE_VERIFIED':sum(bool(r.get('official_match')) for r in staging),
        'VISIBLE_FIRST_PARTY_EMAILS':sum(r.get('email_source_type')=='official_page_visible' and bool(r.get('email_verified_on_official_site')) for r in leads),
        'FULL_EVIDENCE_RECORDS':len(full),'V2_ELIGIBLE_UNSENT':None if offline else len(selected),'SAFE_FSP_UNIQUE_ORGS':None if offline else len(orgs)}
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'metrics':metrics,'eligible_ids':[r['id'] for r in selected], 'full_evidence_ids':full,
        'leads':leads,'staging':staging,'schema':[tuple(r) for r in c.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")],
        'job_runs':[dict(r) for r in c.execute('SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 10')]}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metrics))
    c.close()

if __name__=='__main__':
    main()
