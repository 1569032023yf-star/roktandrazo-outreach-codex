"""Phase 3D controlled validation / Phase 3D 受控验证。

Run only against a newly created development DB copy. No production imports.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ['ROKT_DEV_CONTROLLED_WEB'] = '1'
os.environ['DISCOVERY_PROVIDER'] = 'browser_maps'
os.environ['BROWSER_MAPS_MODE'] = 'direct'
os.environ['SCRAPER_PROXY'] = ''

import json
import sqlite3
import importlib.util
from discovery.discovery_service import DiscoveryService, UrlLibWebsiteFetcher
from discovery.providers.browser_maps import BrowserMapsProvider
from discovery.providers.mock_provider import MockPlacesProvider
from discovery.website_resolver import ProviderWebsiteResolver
from history_crosscheck import cross_check
from dev_fsp import materialize_dev_fsp
from campaign_eligible_v2 import review_campaign_eligible_v2


def main():
    mode, db_name = sys.argv[1:3]
    db = (ROOT / db_name).resolve()
    assert db.is_relative_to(ROOT / '_audit_quarantine' / 'phase3d') and db.exists()
    os.environ['WORKBUDDY_BD_DB_PATH'] = str(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=293').fetchone())
    lead = dict(conn.execute('SELECT * FROM leads WHERE id=1085').fetchone())
    assert row['business_name'] == lead['store_name'] == 'Instant Replay Sports'
    assert not lead['email'] and row['linked_lead_id'] == lead['id']
    checks = cross_check(conn, lead)
    assert not any(checks.get(k) for k in ('previously_sent','hard_bounced','suppressed','unsubscribed','rejected'))
    city = dict(conn.execute('SELECT * FROM retail_city_queue WHERE id=?',(row['active_city_id'],)).fetchone())
    out = {'mode':mode,'merchants_selected':1,'google_maps_requests':0,'official_website_requests':0,
           'dns_mx_lookups':0,'production_db_writes':0,'real_smtp_connections':0,'real_imap_connections':0,
           'scheduler_changes':0,'network_errors':0}
    if mode == 'reproduce':
        spec=importlib.util.spec_from_file_location('phase3c_baseline_service',ROOT/'PHASE3C_RELEASE_PACKAGE/discovery/discovery_service.py')
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        service=module.DiscoveryService(conn,provider=MockPlacesProvider())
        record=json.loads((ROOT/'handoff/phases/PHASE3C_NETWORK_REHEARSAL_RESULT.json').read_text(encoding='utf-8'))['evidence_records'][0]
        ev=record['evidence']
        # Replay previously observed resolution; no fabricated website/email.
        row['website']=record['website']
        conn.execute('UPDATE leads SET official_website=? WHERE id=1085',(row['website'],))
        conn.execute('UPDATE lead_discovery_results SET website=? WHERE id=293',(row['website'],))
        candidate=service._candidate_from_row(row,email=ev['email'],contact_form_url='',
            evidence_url=ev['final_url'],evidence_snippet=ev['visible_text_excerpt'],
            evidence_method='official_homepage',confidence_score='A',status='new',official_match=True)
        candidate.update(official_email_evidence=ev,auto_sendable=1,review_status='hygiene_passed')
        outcome=service._insert_a0_candidate(293,candidate)
        out['bug_reproduced']=outcome[1] is None and conn.execute('SELECT linked_lead_id FROM lead_discovery_results WHERE id=293').fetchone()[0] is None
        out['outcome']=outcome
    else:
        class CountedProvider(BrowserMapsProvider):
            def search_places(self,*args,**kwargs):
                out['google_maps_requests']+=1
                return super().search_places(*args,**kwargs)
        class CountedFetcher(UrlLibWebsiteFetcher):
            def fetch(self,url):
                out['official_website_requests']+=1
                try:
                    return super().fetch(url)
                except Exception:
                    out['network_errors']+=1
                    raise
        provider=CountedProvider()
        service=DiscoveryService(conn,provider=provider)
        # Scope the normal resolution stage to the one authorized fixture merchant.
        pending=list(conn.execute('SELECT id,validation_status FROM lead_discovery_results WHERE active_city_id=? AND id!=293',(city['id'],)))
        conn.execute("UPDATE lead_discovery_results SET validation_status='phase3d_out_of_scope' WHERE active_city_id=? AND id!=293",(city['id'],))
        try:
            out['website_resolution']=service.run_website_resolution(city,ProviderWebsiteResolver(provider),max_results=1).__dict__
        finally:
            conn.executemany('UPDATE lead_discovery_results SET validation_status=? WHERE id=?',[(r[1],r[0]) for r in pending])
        row=dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=293').fetchone())
        out['outcome']=service._postprocess_staged_result(row,city,CountedFetcher())
        staged=dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=293').fetchone())
        evidence=json.loads(staged['raw_payload_json'] or '{}').get('official_email_evidence')
        out['evidence']=evidence
        out['linked_existing_leads']=int(staged['linked_lead_id']==1085 and bool(evidence))
        if out['linked_existing_leads']:
            import dns.resolver
            domain=evidence['email'].split('@')[1]
            out['dns_mx_lookups']+=1
            try:
                answers=dns.resolver.resolve(domain,'MX',lifetime=10)
                mx='ok' if any(str(a.exchange).rstrip('.') for a in answers) else 'null_mx'
            except Exception as exc:
                mx='dns_error'
                out['network_errors']+=1
                out['mx_error']=type(exc).__name__
            current=dict(conn.execute('SELECT * FROM leads WHERE id=1085').fetchone())
            out['mx']=mx
            out['v2']=review_campaign_eligible_v2(current,{'conn':conn,'mx_lookup':{domain:mx}})
            out['fsp']=materialize_dev_fsp(conn,[1085],{domain:mx},'phase3d')
            before=tuple(conn.execute('SELECT COUNT(*),COUNT(DISTINCT organization_key) FROM leads').fetchone())
            second=service._postprocess_staged_result(staged,city,CountedFetcher())
            second_fsp=materialize_dev_fsp(conn,[1085],{domain:mx},'phase3d')
            after=tuple(conn.execute('SELECT COUNT(*),COUNT(DISTINCT organization_key) FROM leads').fetchone())
            out['idempotency_pass']=before==after and second[1]==1085 and second_fsp['inserted']==0
        conn.commit()
    conn.commit()
    target=ROOT/'_audit_quarantine'/'phase3d'/f'{mode}_result.json'
    target.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,default=str))


if __name__=='__main__':
    main()
