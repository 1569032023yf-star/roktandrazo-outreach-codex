import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from local_dashboard_v3_candidate import data, model, places
from local_dashboard_v3_candidate.server import Dashboard, Conflict, handler


class DashboardTests(unittest.TestCase):
    def test_national_catalog_and_truthful_city_history(self):
        from local_dashboard_v3_candidate.server import US_STATES
        all_places = places.load()
        self.assertTrue(US_STATES.issubset({p['state'] for p in all_places}))
        self.assertTrue(any(p['name'] == 'Austin' and p['state'] == 'TX' for p in all_places))
        self.assertTrue(any(p['name'] == 'Lake Placid' and p['state'] == 'NY' for p in all_places))
        fake = [{'id': 7, 'city': 'Lake Placid', 'state': 'NY', 'query_completed': 20}]
        matches = [p for p in places.for_state('NY', fake) if p.get('queue_id') == 7]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['history'], 'recorded')
        self.assertNotIn('count', matches[0])
        fake.append(dict(fake[0], id=8))
        ambiguous = [p for p in places.for_state('NY', fake) if p['name'] == 'Lake Placid']
        self.assertTrue(all(p['history'] == 'ambiguous' for p in ambiguous))

    def test_city_browse_keeps_evidence_and_ambiguous_records_separate(self):
        rows = [dict(id=1, city='Ithaca', state='NY', status='search_matrix_exhausted',
                     completed_at='2026-09-23', query_completed=20, query_recorded=20,
                     candidates=17, last_success_at='2026-09-20')]
        ithaca = [p for p in places.for_state('NY', rows) if p.get('queue_id') == 1]
        self.assertEqual(len(ithaca), 1)
        self.assertEqual(ithaca[0]['queue_status'], 'search_matrix_exhausted')
        self.assertEqual(ithaca[0]['completed_at'], '2026-09-23')
        self.assertEqual(ithaca[0]['candidates'], 17)
        rows.append(dict(rows[0], id=2))
        same_name = [p for p in places.for_state('NY', rows) if p['name'] == 'Ithaca']
        self.assertEqual({p.get('queue_id') for p in same_name}, {None, 1, 2})
        self.assertTrue(all(p['history'] == 'ambiguous' for p in same_name))

    def test_candidate_and_progress_are_not_labeled_as_search_records(self):
        rows = [dict(id=1, city='Lake Placid', state='NY', candidates=3),
                dict(id=2, city='Ithaca', state='NY', last_success_at='2026-01-01'),
                dict(id=3, city='Oneonta', state='NY', started_at='2026-01-01'),
                dict(id=4, city='Corning', state='NY', query_recorded=1)]
        classified = {p['queue_id']: p['history'] for p in places.for_state('NY', rows) if p.get('queue_id')}
        self.assertEqual(classified, {1: 'candidates', 2: 'activity', 3: 'task', 4: 'recorded'})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / 'fixture.db'
        conn = sqlite3.connect(self.db)
        conn.executescript('''
        CREATE TABLE retail_city_queue(id INTEGER,city TEXT,state TEXT,timezone TEXT,priority INTEGER,status TEXT,started_at TEXT,completed_at TEXT,completion_reason TEXT,web_directory_status TEXT,last_success_at TEXT,active_provider TEXT);
        CREATE TABLE lead_discovery_query_state(active_city_id INTEGER,provider TEXT,status TEXT);
        CREATE TABLE lead_discovery_results(id INTEGER,active_city_id INTEGER,business_name TEXT,formatted_address TEXT,city TEXT,state TEXT,phone TEXT,contact_form_url TEXT,website TEXT,source_url TEXT,provider TEXT,query_family TEXT,discovered_at TEXT,last_seen_at TEXT,validation_status TEXT,rejection_reason TEXT,history_crosscheck_result TEXT,linked_lead_id INTEGER,evidence_url TEXT,evidence_snippet TEXT,official_match INTEGER);
        CREATE TABLE leads(id INTEGER,email TEXT,email_source_type TEXT,email_verified_on_official_site INTEGER,evidence_url TEXT,evidence_snippet TEXT,review_reason_code TEXT,review_reason_detail TEXT,status TEXT,organization_key TEXT,sent_at TEXT,replied_at TEXT,unsubscribed_at TEXT);
        CREATE TABLE system_config(secret TEXT);
        INSERT INTO retail_city_queue VALUES(1,'Springfield','TN','America/Chicago',1,'pending',NULL,NULL,NULL,NULL,NULL,NULL);
        INSERT INTO retail_city_queue VALUES(2,'Springfield','IL','America/Chicago',2,'search_matrix_exhausted',NULL,NULL,NULL,NULL,NULL,NULL);
        INSERT INTO lead_discovery_query_state VALUES(1,'browser_maps','completed');
        INSERT INTO lead_discovery_results(id,active_city_id,business_name,validation_status) VALUES(7,1,'Store A','rejected');
        ''')
        conn.commit()
        conn.close()
        self.app = Dashboard(self.root / 'store', self.db, reader=lambda *args: {'data': {}, 'observed_at': data.now(), 'error': None})

    def tearDown(self):
        self.temp.cleanup()

    def test_readonly_and_same_name_cities(self):
        cities = data.catalog(self.db)['cities']
        self.assertEqual({(c['id'], c['state']) for c in cities}, {(1, 'TN'), (2, 'IL')})
        self.assertEqual(data.merchants(self.db, 1)['total'], 1)
        self.assertEqual(data.merchants(self.db, 2)['total'], 0)
        with data.readonly(self.db) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute('SELECT * FROM system_config').fetchall()
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute('DELETE FROM leads')

    def test_draft_revision_duplicates_and_production_unchanged(self):
        item = {'city_id': 1, 'types': '', 'sources': '', 'keywords': '', 'boundary': '',
                'minutes': 30, 'request_limit': 3, 'page_limit': 2}
        plan = {'name': '计划', 'author': '用户', 'concurrency': 3, 'cities': [item]}
        saved = self.app.save_draft({'revision': 0, 'plan': plan})
        self.assertFalse(saved['accepted_by_production'])
        with self.assertRaises(Conflict):
            self.app.save_draft({'revision': 0, 'plan': plan})
        with self.assertRaises(ValueError):
            self.app.save_draft({'revision': 1, 'plan': dict(plan, cities=[item, item])})
        self.assertEqual(data.catalog(self.db)['cities'][1]['status'], 'pending')

    def test_custom_city_draft_and_existing_identity(self):
        def item(name, state, cid=None):
            return {'city_id': cid, 'city_name': name, 'state_code': state, 'types': '', 'sources': '',
                    'keywords': '', 'boundary': '', 'minutes': None, 'request_limit': None, 'page_limit': None}
        plan = {'name': '计划', 'author': '用户', 'concurrency': 1,
                'cities': [item('Austin', 'TX'), item('Springfield', 'TN')]}
        result = self.app.save_draft({'revision': 0, 'plan': plan})
        custom, existing = result['plan']['cities']
        self.assertIsNone(custom['city_id'])
        self.assertEqual((custom['city'], custom['state']), ('Austin', 'TX'))
        self.assertEqual(existing['city_id'], 1)
        self.assertFalse(result['accepted_by_production'])
        plan['cities'] = [item('Springfield', 'TN'), item('Springfield', 'TN', 1)]
        with self.assertRaises(ValueError):
            self.app.save_draft({'revision': 1, 'plan': plan})
        plan['cities'] = [item('Austin', 'XX')]
        with self.assertRaises(ValueError):
            self.app.save_draft({'revision': 1, 'plan': plan})

    def test_failed_refresh_retains_timestamp_but_not_fresh(self):
        self.app.cache['runtime'] = {'data': {'runs': [{'stage': 'inventory'}]}, 'observed_at': data.now(), 'error': None}
        def broken(*args):
            raise OSError('offline')
        self.app.reader = broken
        snapshot = self.app.refresh()
        runtime = snapshot['observations']['runtime']
        self.assertTrue(runtime['error'])
        self.assertFalse(runtime['fresh'])
        self.assertEqual(len(runtime['data']['runs']), 1)
        self.assertIn('observed_at', runtime)

    def test_no_fabricated_run_or_zeros(self):
        record = {'stage': 'inventory', 'actual': 70, 'current_step': '{bad'}
        run = model.runs({'runs': [record]})[0]
        self.assertEqual(run['actual'], 70)
        self.assertEqual(run['counts'], {})
        self.assertIsNone(run['new_organizations'])
        self.assertIsNone(run['city_id'])
        self.assertNotIn('为什么显示 0', str(model.explain({}, run)))

    def test_deferred_not_counted_as_blockers(self):
        city = {'city': {'city_id': 23}, 'completion_checks': {'all_query_families': True, 'pagination_complete': True},
                'blocking_attribution': {'linked_backlog_retry_refs_count': 1, 'linked_backlog_retry_refs': ['ldr:653'],
                                         'auto_recovery_deferred_refs_count': 6, 'auto_recovery_deferred_refs': ['ldr:626']}}
        result = model.explain(city, {'city_id': 23, 'counts': {'places': 0}})
        self.assertIn('1 条', str(result['issues']))
        self.assertIn('6 条', str(result['issues']))
        self.assertNotIn('7 条', str(result['issues']))

    def test_retained_is_read_only_city_scoped_and_reason_filtered(self):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO lead_discovery_results(id,active_city_id,business_name,website,validation_status) VALUES(8,1,'Potential','https://example.com','no_public_email')")
        con.execute("INSERT INTO lead_discovery_results(id,active_city_id,business_name,validation_status) VALUES(9,2,'Other','no_public_email')")
        con.commit(); con.close()
        self.assertEqual(data.retained(self.db, 1, reason='email')['total'], 1)
        self.assertEqual(data.retained(self.db, 1, search='Potential')['total'], 1)
        self.assertEqual(data.retained(self.db, 1, reason='website')['total'], 0)
        self.assertEqual(data.retained(self.db, 2)['total'], 1)
        with self.assertRaises(ValueError):
            data.retained(self.db, 1, reason='invalid')
        self.assertEqual(data.merchants(self.db, 1)['total'], 2)

    def test_facebook_gate_mismatch_is_scoped_to_bridge_blocker(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE lead_discovery_results SET website='https://www.facebook.com/example' WHERE id=7")
        con.commit(); con.close()
        found = data.linked_gate_diagnostics(self.db, 1, ['ldr:7'])
        self.assertEqual(found['items'][0]['kind'], 'facebook_official_gate_mismatch')
        self.assertEqual(data.linked_gate_diagnostics(self.db, 2, ['ldr:7'])['items'], [])
        self.assertEqual(data.linked_gate_diagnostics(self.db, 1, [])['items'], [])

    def test_city_diagnostic_failure_does_not_forge_success(self):
        self.app.db = self.root / 'does-not-exist.db'
        result = self.app.city(1, force=True)
        self.assertFalse(result['diagnostics']['available'])
        self.assertEqual(result['diagnostics']['items'], [])

    def test_gate_explanation_requires_matching_actual_rule_versions(self):
        versions = model.DIAGNOSTIC_HASHES
        health = {'production_code_sha256': dict(versions)}
        city = {'ruleset': {'module_fingerprint': {'sha256': versions['retail_city_queue.py']},
                            'discovery_fingerprint': {'sha256': versions['discovery/discovery_service.py']}}}
        self.assertTrue(model.diagnostic_rules_match(city, health))
        health['production_code_sha256']['discovery/website_resolver.py'] = 'changed'
        self.assertFalse(model.diagnostic_rules_match(city, health))
        self.assertFalse(model.diagnostic_rules_match({}, {}))

    def test_history_totals_distinguish_candidates_and_duplicate_sightings(self):
        con = sqlite3.connect(self.db)
        con.execute('ALTER TABLE lead_discovery_query_state ADD COLUMN duplicate_places INTEGER')
        con.execute('ALTER TABLE lead_discovery_query_state ADD COLUMN provider_errors INTEGER')
        con.execute('UPDATE lead_discovery_query_state SET duplicate_places=5,provider_errors=2')
        con.execute("UPDATE lead_discovery_results SET website='https://example.org',official_match=1 WHERE id=7")
        con.commit(); con.close()
        totals = data.city_history_totals(self.db, 1, 'browser_maps')
        self.assertEqual(totals['candidate_rows'], 1)
        self.assertEqual(totals['candidate_websites'], 1)
        self.assertEqual(totals['official_match_rows'], 1)
        self.assertEqual(totals['duplicate_sightings'], 5)
        self.assertEqual(totals['provider_errors'], 2)

    def test_refresh_uses_only_read_operations(self):
        calls = []
        def reader(name, *args):
            calls.append(name)
            return {'data': {}, 'observed_at': data.now(), 'error': None}
        self.app.reader = reader
        self.app.refresh()
        self.assertCountEqual(calls, ['health', 'runtime', 'provider-audit'])
        self.assertFalse(self.app.snapshot()['capabilities']['submit_plan'])

    def test_http_read_session_and_block_commands(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:' + str(server.server_address[1])
        try:
            with urllib.request.urlopen(base + '/') as response:
                self.assertIn('搜索工作台 V3 候选', response.read().decode())
                cookie = response.headers['Set-Cookie'].split(';')[0]
            with self.assertRaises(urllib.error.HTTPError) as no_session:
                urllib.request.urlopen(base + '/api/snapshot')
            self.assertEqual(no_session.exception.code, 403)
            req = urllib.request.Request(base + '/api/session', headers={'Cookie': cookie})
            with urllib.request.urlopen(req) as response:
                token = json.load(response)['csrf']
            req = urllib.request.Request(base + '/api/refresh', data=b'{}',
                headers={'Cookie': cookie, 'Content-Type': 'application/json', 'X-Dashboard-Token': token})
            with urllib.request.urlopen(req) as response:
                self.assertEqual(len(json.load(response)['observations']['catalog']['data']['cities']), 2)
            req = urllib.request.Request(base + '/api/submit', data=b'{}',
                headers={'Cookie': cookie, 'Content-Type': 'application/json', 'X-Dashboard-Token': token})
            with self.assertRaises(urllib.error.HTTPError) as unknown:
                urllib.request.urlopen(req)
            self.assertEqual(unknown.exception.code, 404)
            req = urllib.request.Request(base + '/api/refresh', data=b'{}',
                headers={'Cookie': cookie, 'Content-Type': 'application/json', 'X-Dashboard-Token': token,
                         'Origin': 'https://outside.example'})
            with self.assertRaises(urllib.error.HTTPError) as origin:
                urllib.request.urlopen(req)
            self.assertEqual(origin.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
