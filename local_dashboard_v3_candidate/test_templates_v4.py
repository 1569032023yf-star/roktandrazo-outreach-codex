import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from local_dashboard_v3_candidate import templates
from local_dashboard_v3_candidate.server import Dashboard, handler


class TemplateWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name) / 'store'

    def tearDown(self):
        self.tmp.cleanup()

    def test_versions_preserve_prior_content_assets_and_do_not_publish(self):
        raw = b'\x89PNG\r\n\x1a\nfixture-content'
        image = templates.save_asset(self.store, {'data': base64.b64encode(raw).decode()})
        first = templates.save(self.store, {'revision': 0, 'subject': 'Hello {{merchant_name}}',
            'html': '<img src="' + image['cid'] + '">', 'text': 'Hello'})
        second = templates.save(self.store, {'revision': 1, 'subject': 'Changed', 'html': '', 'text': 'Text'})
        loaded = templates.read(self.store)
        self.assertFalse(first['production_published'])
        self.assertFalse(second['production_published'])
        self.assertEqual([v['version'] for v in loaded['versions']], [2, 1])
        self.assertEqual(loaded['versions'][1]['subject'], 'Hello {{merchant_name}}')
        self.assertEqual(loaded['versions'][1]['asset_ids'], [image['asset_id']])
        self.assertEqual(base64.b64decode(templates.asset(self.store, image['asset_id'])['data']), raw)
        with self.assertRaises(templates.VersionConflict):
            templates.save(self.store, {'revision': 1, 'subject': 'stale', 'html': '', 'text': ''})

    def test_images_and_subjects_fail_closed(self):
        for data in ('not base64!', base64.b64encode(b'<svg onload=x>').decode()):
            with self.assertRaises(ValueError):
                templates.save_asset(self.store, {'data': data})
        with self.assertRaises(ValueError):
            templates.save(self.store, {'revision': 0, 'subject': 'x\nBcc: x', 'html': '', 'text': ''})
        with self.assertRaises(ValueError):
            templates.save(self.store, {'revision': 0, 'subject': 'x',
                'html': '<img src="cid:' + 'a' * 64 + '@rokt-local">', 'text': ''})
        self.assertEqual(templates.read(self.store)['versions'], [])

    def test_concurrent_writers_have_one_winner(self):
        templates.read(self.store)
        barrier = threading.Barrier(2)
        results = []
        def write(name):
            barrier.wait()
            try:
                templates.save(self.store, {'revision': 0, 'subject': name, 'html': '', 'text': ''})
                results.append('saved')
            except templates.VersionConflict:
                results.append('conflict')
        threads = [threading.Thread(target=write, args=(str(i),)) for i in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertCountEqual(results, ['saved', 'conflict'])
        self.assertEqual(len(templates.read(self.store)['versions']), 1)

    def test_http_requires_session_and_write_token(self):
        app = Dashboard(self.store, self.store / 'unused.db')
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler(app))
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            url = 'http://127.0.0.1:' + str(http.server_port)
            body = json.dumps({'revision': 0, 'subject': 'Hello', 'html': '', 'text': ''}).encode()
            request = urllib.request.Request(url + '/api/template-save', data=body,
                headers={'Content-Type': 'application/json'}, method='POST')
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 403)
            request.add_header('Cookie', 'dashboard_session=' + app.cookie)
            request.add_header('X-Dashboard-Token', app.csrf)
            with urllib.request.urlopen(request) as response:
                saved = json.load(response)
            self.assertFalse(saved['production_published'])
            self.assertEqual(saved['version']['version'], 1)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
