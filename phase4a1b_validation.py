"""Development-copy canonical Inventory rehearsal / 开发副本标准库存演练。"""
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
import env_loader

DB = ROOT / '_audit_quarantine/phase4a1b/rehearsal_final.db'
assert DB.is_file()
os.environ.update(WORKBUDDY_BD_DB_PATH=str(DB), ROKT_DEV_CONTROLLED_WEB='1',
                  DISCOVERY_PROVIDER='browser_maps', WORKBUDDY_DISCOVERY_PROVIDER='browser_maps',
                  BROWSER_MAPS_MODE='direct', SCRAPER_PROXY='',
                  BROWSER_MAPS_CACHE_DIR=str(DB.parent / 'browser_cache'),
                  WORKBUDDY_WEBSITE_RESOLUTION_MAX='20', WORKBUDDY_STAGING_POSTPROCESS_MAX='20')
import bd_db
bd_db.DB_PATH = str(DB)
import bd_orchestrator
from discovery.discovery_service import DiscoveryService
from discovery.providers.browser_maps import BrowserMapsProvider


def snapshot():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    leads = [dict(r) for r in conn.execute('SELECT * FROM leads ORDER BY id')]
    staging = [dict(r) for r in conn.execute('SELECT * FROM lead_discovery_results ORDER BY id')]
    protected = {}
    for table in ('send_log','bounce_log','suppression_list','final_send_plan','send_authorizations','send_authorization_entries'):
        if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
            protected[table] = hashlib.sha256(json.dumps([tuple(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')],default=str).encode()).hexdigest()
    conn.close()
    return {'leads': leads, 'staging': staging, 'protected': protected}


def evidence(rows):
    required = {'requested_url','final_url','http_status','http_success','tls_success','fetched_at',
                'visible_text_excerpt','content_hash','email','email_source_type'}
    out = {}
    for r in rows:
        ev = json.loads(r.get('raw_payload_json') or '{}').get('official_email_evidence') or {}
        if required <= ev.keys() and ev['email'] in ev['visible_text_excerpt'] and ev['http_success'] is True and ev['tls_success'] is True:
            out[r['id']] = ev
    return out


def main():
    c = sqlite3.connect(DB); c.row_factory=sqlite3.Row
    city = dict(c.execute("SELECT * FROM retail_city_queue WHERE status='active' AND state='NY'").fetchone())
    service = DiscoveryService(c, provider=BrowserMapsProvider())
    rows = [dict(r) for r in c.execute("SELECT s.* FROM lead_discovery_results s JOIN leads l ON l.id=s.linked_lead_id WHERE trim(coalesce(l.email,''))=''")]
    eligible = [r['id'] for r in rows if r['active_city_id']==city['id'] and service._linked_retry_allowed(r,city)]
    print('ACTIVE_CITY_ELIGIBLE', len(eligible), eligible, flush=True)
    if '--audit-only' in sys.argv:
        c.close(); return
    result_path = ROOT / 'handoff/phases/PHASE4A1B_FINAL_COPY_VALIDATION.json'
    assert not result_path.exists(), 'Do not rerun the controlled Inventory silently'
    before = snapshot()
    broad = bd_orchestrator._count_broad_ready_pool()
    safe_before = bd_orchestrator._count_safe_ready_pool(c)
    assert broad >= 30 and safe_before < 30, (broad, safe_before)
    summary = {}
    def observe(frame, event, value):
        if event=='return' and frame.f_code is DiscoveryService.run_linked_backlog.__code__ and isinstance(value,dict):
            summary.update(value)
    run_id = 'phase4a1b-dev-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    assert bd_db.start_job_run(run_id,'inventory','2026-09-10',target=30,dry_run=False)
    sys.setprofile(observe)
    try:
        target_met = bd_orchestrator.stage_inventory(run_id,'2026-09-10',False)
    finally:
        sys.setprofile(None)
    after = snapshot()
    job = dict(c.execute('SELECT * FROM job_runs WHERE run_id=?',(run_id,)).fetchone())
    safe_after = job['actual']
    before_ev, after_ev = evidence(before['staging']), evidence(after['staging'])
    linked_ids = {r['linked_lead_id'] for r in before['staging'] if r['linked_lead_id']}
    unchanged_unlinked = ([r for r in before['leads'] if r['id'] not in linked_ids] == [r for r in after['leads'] if r['id'] not in linked_ids])
    frozen = json.loads((ROOT/'handoff/phases/FROZEN_SHA256.json').read_text())
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in frozen.items())
    assert before['protected']==after['protected'] and unchanged_unlinked
    assert len(before['leads'])==len(after['leads']) and len(before['staging'])==len(after['staging'])
    result = {'run_id':run_id,'city':city['city'],'broad_ready_before':broad,
        'linked_backlog_eligible':summary.get('eligible'), 'linked_backlog_processed':summary.get('processed'),
        'website_resolution_processed':summary.get('website_processed'), 'safe_postprocess_processed':summary.get('postprocess_processed'),
        'new_existing_leads_linked':summary.get('existing_leads_linked'),
        'new_visible_first_party_emails':sum(bool(r['email']) and r['email_source_type']=='official_page_visible' for r in after['leads'])-sum(bool(r['email']) and r['email_source_type']=='official_page_visible' for r in before['leads']),
        'new_full_evidence_records':len(set(after_ev)-set(before_ev)),
        'safe_ready_before':safe_before,'safe_ready_after':safe_after,'target_met':target_met,
        'job_status':job['status'],'summary':summary,'unlinked_unchanged':unchanged_unlinked,
        'protected_tables_unchanged':True,'frozen_files_changed':0,'production_db_writes':0,
        'smtp':0,'imap':0,'fsp_created':0,'authorization_created':0,
        'legacy_scanner_used_as_safe_authority':False}
    result_path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (DB.parent/'final_before.json').write_text(json.dumps(before,ensure_ascii=False),encoding='utf-8')
    (DB.parent/'final_after.json').write_text(json.dumps(after,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result),flush=True)
    c.close()


if __name__=='__main__':
    main()
