import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from local_dashboard_v3_candidate import retained_notes
from local_dashboard_v3_candidate.server import Dashboard, handler


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = self.root / 'local'
        self.source = self.root / 'source.db'
        with closing(sqlite3.connect(self.source)) as conn, conn:
            conn.executescript('''
                CREATE TABLE retail_city_queue(id INTEGER PRIMARY KEY,city TEXT,state TEXT);
                CREATE TABLE lead_discovery_results(id INTEGER PRIMARY KEY,active_city_id INTEGER,
                    business_name TEXT,phone TEXT,validation_status TEXT,linked_lead_id INTEGER);
                CREATE TABLE leads(id INTEGER PRIMARY KEY,email TEXT,review_reason_detail TEXT);
                INSERT INTO retail_city_queue VALUES (5,'Town','NY'),(6,'Other','NY');
                INSERT INTO leads VALUES(2,'public@example.test','email evidence pending');
                INSERT INTO lead_discovery_results VALUES
                    (10,5,'Review store','555-0100','manual_review_needed',2),
                    (11,5,'Email pending',NULL,'email_extraction_pending',NULL),
                    (12,5,'Excluded',NULL,'rejected',NULL),
                    (13,6,'Other city',NULL,'manual_review_needed',NULL);
            ''')

    def test_handoff_preserves_records_and_manual_history(self):
        value = {'city_id': 5, 'discovery_id': 10, 'revision': 0, 'website': '',
                 'email': 'manual@example.test', 'contact': '', 'note': 'human note',
                 'evidence': 'human source', 'verified': False}
        retained_notes.save(self.store, self.source, value)
        first = retained_notes.capture_city(self.store, self.source, 5)
        self.assertEqual((first['source_matched'], first['new_snapshots'], first['existing_preserved']), (2, 1, 1))
        self.assertFalse(first['production_updated'])
        self.assertFalse(first['send_authorized'])
        with closing(sqlite3.connect(self.source)) as conn, conn:
            conn.execute("UPDATE lead_discovery_results SET business_name='Changed later' WHERE id=11")
        again = retained_notes.capture_city(self.store, self.source, 5)
        self.assertEqual((again['new_snapshots'], again['existing_preserved']), (0, 2))
        self.assertEqual(again['new_observations'], 1)
        unchanged = retained_notes.capture_city(self.store, self.source, 5)
        self.assertEqual(unchanged['new_observations'], 0)
        with closing(sqlite3.connect(self.source)) as conn, conn:
            conn.execute('DELETE FROM lead_discovery_results WHERE active_city_id=5')
        items = retained_notes.saved_for_city(self.store, 5)['items']
        self.assertEqual([x['id'] for x in items], [10, 11])
        self.assertEqual(items[0]['phone'], '555-0100')
        self.assertEqual(items[1]['business_name'], 'Changed later')
        self.assertEqual((items[1]['search_city'], items[1]['search_state']), ('Town', 'NY'))
        history = retained_notes.read(self.store, self.source, 5, 11)
        self.assertEqual(history['snapshot']['source']['business_name'], 'Email pending')
        self.assertEqual([x['source']['business_name'] for x in history['observations']], ['Changed later', 'Email pending'])
        self.assertEqual(retained_notes.read(self.store, self.source, 5, 10)['versions'][0]['note'], 'human note')
        self.assertEqual(retained_notes.saved_for_city(self.store, 6)['total'], 0)
        with self.assertRaises(ValueError):
            retained_notes.capture_city(self.store, self.source, 7)

    def test_failure_rolls_back_complete_batch(self):
        with closing(retained_notes._connect(self.store)) as conn:
            conn.execute('''CREATE TRIGGER fail_second BEFORE INSERT ON source_snapshots
                WHEN NEW.discovery_id=11 BEGIN SELECT RAISE(ABORT,'test failure'); END''')
            conn.commit()
        with self.assertRaises(sqlite3.DatabaseError):
            retained_notes.capture_city(self.store, self.source, 5)
        self.assertEqual(retained_notes.saved_for_city(self.store, 5)['total'], 0)
        with closing(sqlite3.connect(self.source)) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM lead_discovery_results').fetchone()[0], 4)

    def test_capture_uses_one_consistent_source_snapshot(self):
        with closing(sqlite3.connect(self.source)) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        original = retained_notes._snapshot
        changed = False

        def concurrent_update(source, row):
            nonlocal changed
            if not changed:
                self.assertTrue(source.in_transaction)
                with closing(sqlite3.connect(self.source)) as writer, writer:
                    writer.execute("UPDATE leads SET email='new@example.test' WHERE id=2")
                changed = True
            return original(source, row)

        with patch.object(retained_notes, '_snapshot', side_effect=concurrent_update):
            retained_notes.capture_city(self.store, self.source, 5)
        stored = retained_notes.read(self.store, self.source, 5, 10)['snapshot']['source']
        self.assertEqual(stored['email'], 'public@example.test')
        with closing(sqlite3.connect(self.source)) as conn:
            self.assertEqual(conn.execute('SELECT email FROM leads WHERE id=2').fetchone()[0], 'new@example.test')

    def test_capture_endpoint_requires_local_session_and_token(self):
        app = Dashboard(self.store, self.source)
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler(app))
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{http.server_port}/api/retained-capture'
            req = urllib.request.Request(url, data=json.dumps({'city_id': 5}).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(req)
            self.assertEqual(error.exception.code, 403)
            req.add_header('Cookie', 'dashboard_session=' + app.cookie)
            req.add_header('X-Dashboard-Token', app.csrf)
            with urllib.request.urlopen(req) as response:
                result = json.load(response)
            self.assertEqual(result['new_snapshots'], 2)
            self.assertFalse(result['send_authorized'])
        finally:
            http.shutdown()
            http.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
