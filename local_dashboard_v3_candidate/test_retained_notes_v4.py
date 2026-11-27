import sqlite3
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from contextlib import closing
from http.server import ThreadingHTTPServer
from local_dashboard_v3_candidate import retained_notes
from local_dashboard_v3_candidate.server import Dashboard, handler


class RetainedNotesTests(unittest.TestCase):
    def test_city_list_keeps_source_and_latest_local_annotation_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.db'; store = root / 'local'
            with closing(sqlite3.connect(source)) as conn, conn:
                conn.execute('CREATE TABLE lead_discovery_results(id INTEGER,active_city_id INTEGER,business_name TEXT,website TEXT)')
                conn.execute("INSERT INTO lead_discovery_results VALUES(10,5,'Example','https://source.example.test')")
            value = {'city_id':5, 'discovery_id':10, 'revision':0, 'website':'',
                     'email':'first@example.test', 'contact':'', 'note':'first', 'evidence':'source one', 'verified':False}
            retained_notes.save(store, source, value)
            value.update(revision=1, website='https://manual.example.test', email='second@example.test',
                         note='second', verified=True)
            retained_notes.save(store, source, value)
            item = retained_notes.saved_for_city(store, 5)['items'][0]
            self.assertEqual(item['website'], 'https://source.example.test')
            self.assertEqual(item['local_annotation']['website'], 'https://manual.example.test')
            self.assertEqual(item['local_annotation']['email'], 'second@example.test')
            self.assertEqual(item['local_annotation']['revision'], 2)
            self.assertEqual(item['local_annotation']['verified'], 1)
            self.assertEqual([v['note'] for v in retained_notes.read(store, source, 5, 10)['versions']], ['second','first'])
            with closing(sqlite3.connect(source)) as conn:
                self.assertEqual(conn.execute('SELECT website FROM lead_discovery_results WHERE id=10').fetchone()[0],
                                 'https://source.example.test')

    def test_older_annotations_remain_accessible_when_source_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); store = root / 'local'; source = root / 'missing.db'
            store.mkdir()
            with closing(sqlite3.connect(store / 'retained_notes.sqlite3')) as conn, conn:
                conn.execute('''CREATE TABLE annotations(city_id INTEGER,discovery_id INTEGER,revision INTEGER,
                    created_at TEXT,website TEXT,email TEXT,contact TEXT,note TEXT,evidence TEXT,verified INTEGER,
                    PRIMARY KEY(city_id,discovery_id,revision))''')
                conn.execute("INSERT INTO annotations VALUES(5,10,1,'2026-01-01','','','','old note','',0)")
            self.assertEqual(retained_notes.saved_for_city(store, 5)['items'][0]['id'], 10)
            self.assertEqual(retained_notes.read(store, source, 5, 10)['versions'][0]['note'], 'old note')
            value = {'city_id':5, 'discovery_id':10, 'revision':1, 'website':'', 'email':'',
                     'contact':'', 'note':'new note', 'evidence':'', 'verified':False}
            retained_notes.save(store, source, value)
            self.assertEqual(retained_notes.read(store, source, 5, 10)['versions'][0]['note'], 'new note')

    def test_saved_snapshot_and_history_survive_source_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.db'; store = root / 'local'
            with closing(sqlite3.connect(source)) as conn, conn:
                conn.execute('''CREATE TABLE lead_discovery_results(id INTEGER,active_city_id INTEGER,
                    business_name TEXT,formatted_address TEXT,city TEXT,state TEXT,website TEXT,
                    source_url TEXT,discovered_at TEXT,validation_status TEXT,linked_lead_id INTEGER)''')
                conn.execute('CREATE TABLE leads(id INTEGER,email TEXT,review_reason_detail TEXT)')
                conn.execute("INSERT INTO leads VALUES(2,'public@example.test','missing proof')")
                conn.execute("INSERT INTO lead_discovery_results VALUES(10,5,'Example','123 Main','Town','NY',"
                             "'https://example.test','https://source.test','2026-01-01','manual_review_needed',2)")
            value = {'city_id':5, 'discovery_id':10, 'revision':0, 'website':'', 'email':'',
                     'contact':'', 'note':'first', 'evidence':'source checked', 'verified':False}
            retained_notes.save(store, source, value)
            with closing(sqlite3.connect(source)) as conn, conn:
                conn.execute('DELETE FROM lead_discovery_results')
            items = retained_notes.saved_for_city(store, 5)['items']
            self.assertEqual((items[0]['business_name'],items[0]['email']), ('Example','public@example.test'))
            value.update(revision=1, note='second')
            retained_notes.save(store, source, value)
            self.assertEqual([v['note'] for v in retained_notes.read(store, source, 5, 10)['versions']],
                             ['second','first'])
            self.assertEqual(retained_notes.saved_for_city(store, 6)['total'], 0)
            with self.assertRaises(ValueError):
                retained_notes.read(store, source, 6, 10)

    def test_append_only_versions_stay_local_and_require_matching_city(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.db'
            with closing(sqlite3.connect(source)) as conn, conn:
                conn.execute('CREATE TABLE lead_discovery_results(id INTEGER, active_city_id INTEGER, business_name TEXT)')
                conn.execute("INSERT INTO lead_discovery_results VALUES(10, 5, 'Example')")
            value = {'city_id': 5, 'discovery_id': 10, 'revision': 0,
                     'website': 'https://example.test', 'email': 'store@example.test',
                     'contact': 'public phone', 'note': 'looked up by hand',
                     'evidence': 'official contact page', 'verified': False}
            result = retained_notes.save(root / 'local', source, value)
            self.assertFalse(result['production_updated'])
            self.assertFalse(result['send_authorized'])
            with self.assertRaises(retained_notes.VersionConflict):
                retained_notes.save(root / 'local', source, value)
            value.update(revision=1, email='new@example.test', verified=True)
            retained_notes.save(root / 'local', source, value)
            versions = retained_notes.read(root / 'local', source, 5, 10)['versions']
            self.assertEqual([v['revision'] for v in versions], [2, 1])
            self.assertEqual(versions[1]['email'], 'store@example.test')
            with self.assertRaises(ValueError):
                retained_notes.read(root / 'local', source, 6, 10)
            with closing(sqlite3.connect(source)) as conn:
                self.assertEqual(conn.execute('SELECT * FROM lead_discovery_results').fetchall(), [(10, 5, 'Example')])

    def test_rejects_untrusted_url_and_newline_email(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.db'
            with closing(sqlite3.connect(source)) as conn, conn:
                conn.execute('CREATE TABLE lead_discovery_results(id INTEGER, active_city_id INTEGER)')
                conn.execute('INSERT INTO lead_discovery_results VALUES(10,5)')
            value = {'city_id': 5, 'discovery_id': 10, 'revision': 0, 'website': 'javascript:alert(1)',
                     'email': '', 'contact': '', 'note': '', 'evidence': '', 'verified': False}
            with self.assertRaises(ValueError):
                retained_notes.save(root / 'local', source, value)
            value.update(website='', email='x\nBcc: someone')
            with self.assertRaises(ValueError):
                retained_notes.save(root / 'local', source, value)
            self.assertEqual(retained_notes.read(root / 'local', source, 5, 10)['versions'], [])

    def test_http_notes_require_session_and_write_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.db'
            with closing(sqlite3.connect(source)) as conn, conn:
                conn.execute('CREATE TABLE lead_discovery_results(id INTEGER, active_city_id INTEGER)')
                conn.execute('INSERT INTO lead_discovery_results VALUES(10,5)')
            app = Dashboard(root / 'local', source)
            http = ThreadingHTTPServer(('127.0.0.1', 0), handler(app))
            thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
            try:
                url = 'http://127.0.0.1:' + str(http.server_port) + '/api/retained-notes'
                value = {'city_id':5, 'discovery_id':10, 'revision':0, 'website':'', 'email':'',
                         'contact':'', 'note':'local only', 'evidence':'', 'verified':False}
                req = urllib.request.Request(url, data=json.dumps(value).encode(),
                    headers={'Content-Type':'application/json'}, method='POST')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(req)
                self.assertEqual(error.exception.code, 403)
                req.add_header('Cookie', 'dashboard_session=' + app.cookie)
                req.add_header('X-Dashboard-Token', app.csrf)
                with urllib.request.urlopen(req) as response:
                    result = json.load(response)
                self.assertFalse(result['production_updated'])
                self.assertEqual(result['revision'], 1)
            finally:
                http.shutdown(); http.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
