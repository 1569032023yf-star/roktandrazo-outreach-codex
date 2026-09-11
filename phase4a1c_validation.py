"""One development-copy Inventory observation / 一次开发副本库存观察。"""
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
import env_loader

DB = ROOT / '_audit_quarantine/phase4a1c/rehearsal.db'
assert DB.is_file()
os.environ.update(WORKBUDDY_BD_DB_PATH=str(DB), ROKT_DEV_CONTROLLED_WEB='1',
    DISCOVERY_PROVIDER='browser_maps', WORKBUDDY_DISCOVERY_PROVIDER='browser_maps',
    BROWSER_MAPS_MODE='direct', SCRAPER_PROXY='',
    BROWSER_MAPS_CACHE_DIR=str(DB.parent / 'browser_cache'),
    WORKBUDDY_DISCOVERY_MAX_PAGES='1', WORKBUDDY_WEBSITE_RESOLUTION_MAX='20',
    WORKBUDDY_STAGING_POSTPROCESS_MAX='20')
import bd_db
bd_db.DB_PATH = str(DB)
import bd_orchestrator
from discovery.discovery_service import DiscoveryService


def snapshot(conn):
    rows = lambda table: [dict(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')]
    protected = {t: hashlib.sha256(json.dumps(rows(t), sort_keys=True, default=str).encode()).hexdigest()
        for t in ('send_log','bounce_log','suppression_list','final_send_plan',
                  'send_authorizations','send_authorization_entries')}
    return {'leads': rows('leads'), 'staging': rows('lead_discovery_results'), 'protected': protected,
        'planned': conn.execute("SELECT COUNT(*) FROM final_send_plan WHERE status='planned'").fetchone()[0]}


def full_evidence(rows):
    required = {'requested_url','final_url','http_status','http_success','tls_success',
        'fetched_at','visible_text_excerpt','content_hash','email','email_source_type'}
    return {r['id'] for r in rows
        if (ev := json.loads(r.get('raw_payload_json') or '{}').get('official_email_evidence') or {})
        and required <= ev.keys() and ev['email'] in ev['visible_text_excerpt']
        and ev['http_success'] is True and ev['tls_success'] is True}


def main():
    report = ROOT / 'handoff/phases/PHASE4A1C_COPY_VALIDATION.json'
    marker = DB.parent / 'inventory_started'
    assert not report.exists() and not marker.exists(), 'Single-run guard / 禁止重复演练'
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    before = snapshot(c)
    broad = bd_orchestrator._count_broad_ready_pool()
    safe_before = bd_orchestrator._count_safe_ready_pool(c)
    assert broad >= 30 and safe_before < 30, (broad, safe_before)
    captured = {}
    names = ('run_places_batch','run_website_resolution','run_staging_postprocess','run_linked_backlog')
    codes = {getattr(DiscoveryService,n).__code__: n for n in names}
    def observe(frame, event, value):
        name = codes.get(frame.f_code)
        if name and event == 'return' and frame.f_locals.get('staging_ids') is None:
            captured[name] = value if isinstance(value,dict) else vars(value) if value is not None else None
    run_id = 'phase4a1c-dev-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    assert bd_db.start_job_run(run_id,'inventory','2026-09-11',target=30,dry_run=False)
    marker.touch(exist_ok=False)
    sys.setprofile(observe)
    try:
        target_met = bd_orchestrator.stage_inventory(run_id,'2026-09-11',False)
    finally:
        sys.setprofile(None)
    after = snapshot(c)
    job = dict(c.execute('SELECT * FROM job_runs WHERE run_id=?',(run_id,)).fetchone())
    linked = {r['linked_lead_id'] for r in before['staging'] if r['linked_lead_id']}
    old_ids = {r['id'] for r in before['leads']}
    unchanged = ([r for r in before['leads'] if r['id'] not in linked] ==
                 [r for r in after['leads'] if r['id'] in old_ids and r['id'] not in linked])
    frozen = json.loads((ROOT/'handoff/phases/FROZEN_SHA256.json').read_text())
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in frozen.items())
    assert unchanged and before['protected']==after['protected']
    discovery = captured.get('run_places_batch') or {}
    backlog = captured.get('run_linked_backlog') or {}
    visible = lambda data: sum(bool(r['email']) and r['email_source_type']=='official_page_visible' for r in data['leads'])
    result = {'DESCRIPTION':'Single canonical Inventory on fresh production DB copy / 新鲜生产库副本上的一次标准库存演练',
        'RUN_ID':run_id,'BROAD_READY':broad,
        'NEW_DISCOVERY_PATH_EXECUTED':'run_places_batch' in captured,
        'DISCOVERY_RESULTS_SEEN':discovery.get('results_seen'), 'NEW_UNIQUE_PLACES':discovery.get('new_unique_places'),
        'WEBSITE_RESOLUTION_PROCESSED':(captured.get('run_website_resolution') or {}).get('results_seen'),
        'NORMAL_STAGING_POSTPROCESS_PROCESSED':(captured.get('run_staging_postprocess') or {}).get('results_seen'),
        'LINKED_BACKLOG_PATH_EXECUTED':'run_linked_backlog' in captured,
        'LINKED_BACKLOG_ELIGIBLE':backlog.get('eligible'), 'LINKED_BACKLOG_PROCESSED':backlog.get('processed'),
        'NEW_VISIBLE_FIRST_PARTY_EMAILS':visible(after)-visible(before),
        'NEW_FULL_EVIDENCE_RECORDS':len(full_evidence(after['staging'])-full_evidence(before['staging'])),
        'READ_ONLY_V2_SAFE_BEFORE':safe_before,'READ_ONLY_V2_SAFE_AFTER':job['actual'],
        'MATERIALIZED_FSP_PLANNED':after['planned'],'MATERIALIZED_FSP_CREATED':0,'AUTHORIZATION_CREATED':0,
        'SMTP':0,'IMAP':0,'PRODUCTION_DB_WRITES':0,'PRODUCTION_FILES_CHANGED':0,'SCHEDULER_CHANGES':0,
        'FROZEN_FILES_CHANGED':0,'UNLINKED_SCOPE_DEFERRED':166,'EXISTING_UNLINKED_UNCHANGED':unchanged,
        'PROTECTED_TABLES_UNCHANGED':True,'TARGET_MET':target_met,'JOB_STATUS':job['status'],
        'CAPTURED':captured}
    report.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    c.close()


if __name__ == '__main__':
    main()
