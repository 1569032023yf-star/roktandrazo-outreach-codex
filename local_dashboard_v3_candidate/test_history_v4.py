import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from local_dashboard_v3_candidate import history


class HistoricalInventoryTests(unittest.TestCase):
    def test_city_request_audit_is_paginated_scoped_and_does_not_invent_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'history.db'
            con = sqlite3.connect(db)
            con.execute('''CREATE TABLE provider_request_audit(id INTEGER PRIMARY KEY,active_city_id INTEGER,
                requested_at TEXT,provider TEXT,query_family TEXT,source_query TEXT,status TEXT,
                request_count INTEGER,result_count INTEGER,error TEXT)''')
            con.executemany('INSERT INTO provider_request_audit VALUES(?,?,?,?,?,?,?,?,?,?)', [
                (i, 7 if i <= 51 else 8, f'2026-10-{(i-1)%28+1:02}T00:00:00+00:00',
                 'maps', 'toys', 'toys Alpha NY', 'configuration_blocked' if i == 1 else 'ok',
                 0 if i == 1 else 1, 0 if i == 1 else 3, 'private error') for i in range(1, 53)])
            con.commit(); con.close()
            first = history.city_request_audit(db, 7)
            last = history.city_request_audit(db, 7, 2)
            self.assertEqual((first['total'], len(first['items']), len(last['items'])), (51, 50, 1))
            self.assertEqual(len({r['id'] for r in first['items'] + last['items']}), 51)
            self.assertNotIn('error', first['items'][0])
            self.assertNotIn('run_id', first['items'][0])
            self.assertEqual(history.city_request_audit(db, 8)['total'], 1)
            self.assertEqual(history.city_request_audit(db, 9)['total'], 0)
            with self.assertRaises(ValueError):
                history.city_request_audit(db, -1)
            with self.assertRaises(ValueError):
                history.city_request_audit(db, 7, 0)

    def test_report_snapshots_stay_unattributed_and_keep_unknown_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'inventory_final_report_20260723_1135.json').write_text(json.dumps({
                'updated_at':'2026-07-23T11:35:00+08:00', 'status':'failed',
                'candidates_discovered':19, 'candidates_verified':True, 'a0_added':0,
                'private_field':'must not be returned'}), encoding='utf-8')
            (out / 'inventory_final_report_20260723_1136.json').write_text('{invalid', encoding='utf-8')
            (out / 'inventory_final_report_other.json').write_text('{}', encoding='utf-8')
            result = history.report_snapshots(out)
            self.assertEqual(len(result['items']), 1)
            self.assertEqual(result['unreadable'], 1)
            item = result['items'][0]
            self.assertEqual(item['candidates_discovered'], 19)
            self.assertIsNone(item['candidates_verified'])
            self.assertIsNone(item['run_id'])
            self.assertIsNone(item['city'])
            self.assertEqual(item['run_kind'], '未知')
            self.assertNotIn('private_field', item)
            self.assertFalse(history.report_snapshots(out / 'missing')['available'])

    def test_only_unambiguous_recorded_city_attribution_and_no_fake_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'history.db'
            con = sqlite3.connect(db)
            con.execute('CREATE TABLE job_runs(run_id TEXT,stage TEXT,started_at TEXT,finished_at TEXT,status TEXT,current_step TEXT,dry_run INTEGER)')
            con.execute('CREATE TABLE retail_city_queue(id INTEGER,city TEXT,state TEXT)')
            con.execute("INSERT INTO retail_city_queue VALUES(7,'Alpha','NY')")
            def trace(*ids):
                return json.dumps({'schema': 'rokt.inventory_stage_trace.v1', 'events':
                    [{'phase': 'places', 'outcome': 'enter', 'city_id': i} for i in ids]})
            con.executemany('INSERT INTO job_runs VALUES(?,?,?,?,?,?,?)', [
                ('one', 'inventory', '2026-07-01', '2026-07-01', 'completed', trace(7, 7), 0),
                ('ambiguous', 'inventory', '2026-07-02', None, 'stopped', trace(7, 8), 0),
                ('unknown', 'inventory', '2026-07-03', None, 'stopped', '{bad', 0),
                ('simulation', 'inventory', '2026-07-04', None, 'completed', trace(7), 1),
                ('other', 'outreach', '2026-07-05', None, 'completed', trace(7), 0)])
            con.commit(); con.close()
            all_rows = history.inventory(db)
            self.assertEqual(all_rows['total'], 4)
            city_rows = history.inventory(db, city_id=7)
            self.assertEqual({r['run_id'] for r in city_rows['items']}, {'one', 'simulation'})
            self.assertTrue(all(r['new_merchants'] is None for r in city_rows['items']))
            self.assertEqual(city_rows['items'][0]['kind'], '模拟作业')
            self.assertEqual(next(r for r in all_rows['items'] if r['run_id'] == 'ambiguous')['city_id'], None)
            with self.assertRaises(ValueError):
                history.inventory(db, city_id=-1)

    def test_log_attribution_requires_exact_run_and_unambiguous_city(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); db = root / 'history.db'; out = root / 'output'; out.mkdir()
            con = sqlite3.connect(db)
            con.execute('CREATE TABLE job_runs(run_id TEXT,stage TEXT,started_at TEXT,finished_at TEXT,status TEXT,current_step TEXT,dry_run INTEGER)')
            con.execute('CREATE TABLE retail_city_queue(id INTEGER,city TEXT,state TEXT)')
            con.execute("INSERT INTO retail_city_queue VALUES(7,'Alpha','NY')")
            con.execute("INSERT INTO job_runs VALUES('inventory:2026-07-01:abc','inventory','2026-07-01',NULL,'completed','starting',0)")
            con.commit(); con.close()
            (out / '_canary_run_a.log').write_text('BD Orchestrator | stage=inventory | dry_run=False\nrun_id: inventory:2026-07-01:abc\nActive city: Alpha, NY; work\nNEW_UNIQUE_PLACES=4', encoding='utf-8')
            result = history.inventory(db, city_id=7, output=out)
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['items'][0]['new_places'], 4)
            self.assertIsNone(result['items'][0]['new_merchants'])
            (out / '_canary_run_b.log').write_text('BD Orchestrator | stage=inventory | dry_run=False\nrun_id: inventory:2026-07-01:abc\nActive city: Alpha, NY; work\nNEW_UNIQUE_PLACES=9', encoding='utf-8')
            self.assertIsNone(history.inventory(db, city_id=7, output=out)['items'][0]['new_places'])

    def test_older_retail_city_logs_require_scoped_matching_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); db = root / 'history.db'; out = root / 'output'; out.mkdir()
            con = sqlite3.connect(db)
            con.execute('CREATE TABLE job_runs(run_id TEXT,stage TEXT,started_at TEXT,finished_at TEXT,status TEXT,current_step TEXT,dry_run INTEGER)')
            con.execute('CREATE TABLE retail_city_queue(id INTEGER,city TEXT,state TEXT)')
            con.executemany('INSERT INTO retail_city_queue VALUES(?,?,?)', [(7,'Alpha','NY'), (8,'Beta','TN')])
            con.executemany('INSERT INTO job_runs VALUES(?,?,?,?,?,?,?)', [
                ('inventory:2026-08-21:a','inventory','2026-08-21',None,'completed','starting',0),
                ('inventory:2026-09-02:b','inventory','2026-09-02',None,'completed','starting',0)])
            con.commit(); con.close()
            prefix = 'BD Orchestrator | stage=inventory | dry_run=False\n'
            (out / 'inventory_2026-08-21.log').write_text(prefix + 'run_id: inventory:2026-08-21:a\nActive retail city (state scope=NY): Alpha, NY (no city switching)', encoding='utf-8')
            (out / 'p24c_inventory_run.log').write_text(prefix + 'run_id: inventory:2026-09-02:b\nActive retail city: Beta, TN (no city switching)', encoding='utf-8')
            self.assertEqual(history.inventory(db, city_id=7, output=out)['total'], 1)
            self.assertEqual(history.inventory(db, city_id=8, output=out)['total'], 1)
            # A conflicting state scope or additional city cannot be guessed away.
            (out / 'p24c_inventory_run.log').write_text(prefix + 'run_id: inventory:2026-09-02:b\nActive retail city (state scope=NY): Beta, TN (no city switching)', encoding='utf-8')
            self.assertEqual(history.inventory(db, city_id=8, output=out)['total'], 0)
            (out / 'inventory_2026-08-21.log').write_text(prefix + 'run_id: inventory:2026-08-21:a\nActive retail city: Alpha, NY (no city switching)\nActive city: Beta, TN', encoding='utf-8')
            self.assertEqual(history.inventory(db, city_id=7, output=out)['total'], 0)


if __name__ == '__main__':
    unittest.main()
