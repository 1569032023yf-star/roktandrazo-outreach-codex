"""Offline fault injection: no Playwright, network, production DB or SMTP."""
import contextlib
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from discovery.providers.provider_diagnostics import classify, safe_error, ErrorCode, ProviderFailure
from discovery.providers import browser_maps as provider
from discovery.providers import browser_maps_scraper as scraper

SECRET = 'Token=fixture-secret Cookie=private https://proxy.invalid:8888/customer?key=secret'


class Resource:
    def __init__(self, failure=None):
        self.closed = 0
        self.failure = failure
    def close(self):
        self.closed += 1
        if self.failure:
            raise self.failure


class FakePage(Resource):
    url = 'https://maps.invalid/fixture'
    def __init__(self, text='No results found', goto_failure=None, status=200, feed=False, challenge=False, cards=None, wait_failure=None):
        super().__init__()
        self.text, self.goto_failure, self.status = text, goto_failure, status
        self.feed, self.challenge = feed, challenge
        self.cards, self.wait_failure = cards or [], wait_failure
        self.navigations = 0
    def goto(self, *args, **kwargs):
        self.navigations += 1
        if self.goto_failure:
            raise self.goto_failure
        return SimpleNamespace(status=self.status)
    def inner_text(self, selector): return self.text
    def query_selector(self, selector):
        if 'recaptcha' in selector: return object() if self.challenge else None
        if selector == '[role="feed"]': return self if self.feed else None
        return None
    def query_selector_all(self, selector): return self.cards
    def wait_for_selector(self, *args, **kwargs):
        if self.wait_failure: raise self.wait_failure
    def evaluate(self, *args): pass


class Harness:
    def __init__(self, page=None, launch_failure=None, context_failure=None, page_failure=None):
        self.page = page or FakePage()
        self.browser, self.context = Resource(), Resource()
        self.stopped = 0
        self.launch_failure, self.context_failure, self.page_failure = launch_failure, context_failure, page_failure
        self.browser.new_context = self.new_context
        self.context.new_page = self.new_page
        self.pw = SimpleNamespace(chromium=SimpleNamespace(launch=self.launch))
    def launch(self, **kwargs):
        self.launch_options = kwargs
        if self.launch_failure: raise self.launch_failure
        return self.browser
    def new_context(self, **kwargs):
        if self.context_failure: raise self.context_failure
        return self.context
    def new_page(self):
        if self.page_failure: raise self.page_failure
        return self.page
    @contextlib.contextmanager
    def factory(self):
        try: yield self.pw
        finally: self.stopped += 1
    def run(self, **kwargs):
        return scraper.scrape_google_maps(SECRET, 'Fixture City', 'NY', playwright_factory=self.factory, sleep=lambda _: None, **kwargs)


class DiagnosticsTests(unittest.TestCase):
    def test_exact_exception_evidence_and_unknown(self):
        cases = [
            (RuntimeError('net::ERR_PROXY_CONNECTION_FAILED '+SECRET), 'NAVIGATION', 'PROXY_CONNECTION_ERROR'),
            (RuntimeError('net::ERR_TUNNEL_CONNECTION_FAILED '+SECRET), 'NAVIGATION', 'PROXY_CONNECTION_ERROR'),
            (RuntimeError('net::ERR_NAME_NOT_RESOLVED '+SECRET), 'NAVIGATION', 'DNS_RESOLUTION_ERROR'),
            (socket.gaierror(1, SECRET), 'NAVIGATION', 'DNS_RESOLUTION_ERROR'),
            (TimeoutError(SECRET), 'NAVIGATION', 'NETWORK_TIMEOUT'),
            (RuntimeError('net::ERR_TIMED_OUT '+SECRET), 'NAVIGATION', 'NETWORK_TIMEOUT'),
            (RuntimeError('proxy timeout blocked '+SECRET), 'NAVIGATION', 'UNKNOWN_PROVIDER_ERROR'),
            (ValueError(SECRET), 'PARSE', 'UNKNOWN_PROVIDER_ERROR'),
            (RuntimeError(SECRET), 'LAUNCH', 'BROWSER_LAUNCH_ERROR'),
            (ModuleNotFoundError(SECRET, name='playwright.sync_api'), 'IMPORT', 'BROWSER_LAUNCH_ERROR'),
            (ModuleNotFoundError(SECRET, name='unrelated'), 'IMPORT', 'UNKNOWN_PROVIDER_ERROR'),
        ]
        for exc, stage, expected in cases:
            with self.subTest(expected=expected, stage=stage):
                self.assertEqual(str(classify(exc, stage)), expected+':'+stage)
        closed = type('TargetClosedError', (Exception,), {'__module__':'playwright._impl._errors'})
        self.assertEqual(classify(closed(SECRET), 'NAVIGATION').code, ErrorCode.BROWSER_PROCESS_EXITED)

    def test_wire_contract_cannot_echo_untrusted_diagnostics(self):
        for value in [SECRET, {'error': SECRET}, 'NETWORK_TIMEOUT:NAVIGATION '+SECRET, 'SOMETHING:NAVIGATION']:
            self.assertEqual(safe_error(value), 'UNKNOWN_PROVIDER_ERROR:UNKNOWN')
        self.assertEqual(safe_error('NETWORK_TIMEOUT:NAVIGATION'), 'NETWORK_TIMEOUT:NAVIGATION')

    def test_missing_playwright(self):
        import builtins
        original = builtins.__import__
        def importer(name, *args, **kwargs):
            if name == 'playwright.sync_api':
                raise ModuleNotFoundError(SECRET, name='playwright.sync_api')
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=importer):
            result = scraper.scrape_google_maps('fixture')
        self.assertEqual(result['error'], 'BROWSER_LAUNCH_ERROR:IMPORT')

    def test_launch_and_partial_initialization_cleanup(self):
        for point in ('launch_failure', 'context_failure', 'page_failure'):
            h = Harness(**{point: RuntimeError(SECRET)})
            result = h.run()
            self.assertNotEqual(result['status'], 'ok')
            self.assertEqual(h.stopped, 1)
            self.assertEqual(h.browser.closed, 0 if point == 'launch_failure' else 1)
            self.assertEqual(h.context.closed, 1 if point == 'page_failure' else 0)

    def test_navigation_failures_are_redacted_and_closed(self):
        for exc in [TimeoutError(SECRET), RuntimeError('net::ERR_PROXY_CONNECTION_FAILED '+SECRET), RuntimeError(SECRET)]:
            h = Harness(FakePage(goto_failure=exc))
            out = io.StringIO()
            with contextlib.redirect_stdout(out): result = h.run()
            self.assertNotEqual(result['status'], 'ok')
            self.assertNotIn(SECRET, out.getvalue()+result['error'])
            self.assertEqual([h.page.closed, h.context.closed, h.browser.closed, h.stopped], [1]*4)

    def test_source_429_403_challenge_stop_without_parsing(self):
        for status, challenge, code in [(429,False,'SOURCE_RATE_LIMITED'), (403,False,'SOURCE_ACCESS_RESTRICTED'), (200,True,'SOURCE_VERIFICATION_REQUIRED'), (500,False,'UNKNOWN_PROVIDER_ERROR')]:
            h = Harness(FakePage(text='fixture', status=status, challenge=challenge))
            with patch.object(scraper, 'extract_direct_place_data') as parse:
                result = h.run()
            self.assertEqual(result['error'], code+':SOURCE_CHECK')
            parse.assert_not_called()
            self.assertEqual(h.page.navigations, 1)
            self.assertFalse(result['results'])
            self.assertNotIn('--disable-blink-features=AutomationControlled', h.launch_options['args'])

    def test_normal_empty_is_success_and_releases_every_resource(self):
        h = Harness()
        result = h.run()
        self.assertEqual((result['status'],result['results'],result['error'],result['next_page_cursor']), ('ok',[], '', ''))
        self.assertEqual([h.page.closed,h.context.closed,h.browser.closed,h.stopped],[1]*4)

    def test_no_unproven_empty_result(self):
        for feed, code in [(True, 'DOM_LAYOUT_CHANGED'),(False,'NETWORK_TIMEOUT')]:
            h = Harness(FakePage(text='fixture',feed=feed,wait_failure=TimeoutError(SECRET)))
            result = h.run()
            self.assertEqual(result['error'], code+':DOM')
            self.assertNotEqual(result['status'], 'ok')

    def test_parse_error_and_partial_result(self):
        valid = {'business_name':'Fixture Store','category':'store'}
        h = Harness(FakePage(text='fixture',cards=[object(),object()]))
        with patch.object(scraper,'extract_place_data_from_card',side_effect=[valid,ProviderFailure(ErrorCode.RESULT_PARSE_ERROR,'PARSE')]):
            result = h.run()
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['error'],'RESULT_PARSE_ERROR:PARSE')
        self.assertEqual(len(result['results']),1)
        self.assertEqual(result['next_page_cursor'],'')

    def test_direct_success_has_normalized_identity(self):
        h = Harness(FakePage(text='fixture'))
        with patch.object(scraper,'extract_direct_place_data',return_value={'business_name':'Fixture Store','website':'https://fixture.test','google_maps_url':'https://maps.invalid/place'}):
            result = h.run()
        self.assertEqual(result['status'],'ok')
        self.assertTrue(result['results'][0]['place_id'])
        self.assertEqual(result['results'][0]['city'],'Fixture City')

    def test_card_exception_is_explicit_parse_failure(self):
        card = SimpleNamespace(query_selector=lambda _: (_ for _ in ()).throw(ValueError(SECRET)))
        with self.assertRaises(ProviderFailure) as caught:
            scraper.extract_place_data_from_card(card)
        self.assertEqual(str(caught.exception),'RESULT_PARSE_ERROR:PARSE')

    def test_cleanup_failure_does_not_skip_other_cleanup_or_primary_error(self):
        h = Harness(FakePage(goto_failure=TimeoutError(SECRET)))
        h.page.failure = RuntimeError(SECRET)
        h.context.failure = RuntimeError(SECRET)
        result = h.run()
        self.assertEqual(result['error'],'NETWORK_TIMEOUT:NAVIGATION')
        self.assertEqual([h.page.closed,h.context.closed,h.browser.closed,h.stopped],[1]*4)
        self.assertEqual(len(result['errors']),3)

    def test_cleanup_failure_on_success_is_not_ok(self):
        h = Harness()
        h.context.failure = RuntimeError(SECRET)
        self.assertEqual(h.run()['error'],'UNKNOWN_PROVIDER_ERROR:CLEANUP')

    def test_detail_failure_is_not_silent_empty_fields(self):
        page = FakePage(goto_failure=TimeoutError(SECRET))
        with self.assertRaises(ProviderFailure) as caught:
            scraper.extract_detail_fields(page, 'https://maps.invalid/place')
        self.assertEqual(str(caught.exception),'NETWORK_TIMEOUT:DETAIL')


class CacheContractTests(unittest.TestCase):
    def test_shape_faults_fail_closed(self):
        base = {'status':'ok','results':[{'business_name':'Fixture'}]}
        faults = [None, [], {}, {'results':None}, {'results':['bad']}, {'results':[{}]},
                  {**base,'request_count':True},{**base,'cost_units':-1},{**base,'next_page_cursor':42},
                  {'results':[{'business_name':'Fixture','types':'store'}]},
                  {'results':[{'business_name':'Fixture','raw_payload':[]}]},
                  {'results':[{'business_name':['bad']}]},
                  {'results':[{'business_name':'Fixture','website':{'token':SECRET}}]}]
        for raw in faults:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as td:
                path = Path(td)/provider._cache_key('q','c','s','0')
                path.write_text(json.dumps(raw),encoding='utf8')
                page = provider.BrowserMapsProvider(cache_dir=td,mode='direct').search_places('q','c','s')
                self.assertFalse(page.ok)
                self.assertEqual(page.error,'CACHE_READ_ERROR:CACHE_READ')
                self.assertFalse(page.results)

    def test_success_with_failure_evidence_is_rejected(self):
        for status in ({}, {'status': 'ok'}):
            for evidence in ({'error': 'UNKNOWN_PROVIDER_ERROR:PARSE'},
                             {'errors': ['RESULT_PARSE_ERROR:PARSE']}):
                with self.subTest(status=status, evidence=evidence):
                    with self.assertRaises(ProviderFailure):
                        provider._page_from_raw({'results': [], **status, **evidence},
                                                'q', 'c', 's', cache=True)

    def test_bad_json_and_missing_file_are_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            p = provider.BrowserMapsProvider(cache_dir=td)
            path = Path(td)/'fixture.json'
            path.write_text(SECRET,encoding='utf8')
            self.assertEqual(p._load_from_json_file(str(path),'q','c','s').error,'CACHE_READ_ERROR:CACHE_READ')
            self.assertEqual(p._load_from_json_file(str(path)+'missing','q','c','s').error,'CACHE_READ_ERROR:CACHE_READ')

    def test_isolated_empty_cache_replayed_without_network_or_global_cache(self):
        with tempfile.TemporaryDirectory() as td, patch.object(provider,'_scrape_direct') as live:
            path = Path(td)/provider._cache_key('q','c','s','0')
            path.write_text(json.dumps({'results':[],'status':'ok'}),encoding='utf8')
            p = provider.BrowserMapsProvider(cache_dir=td,mode='direct')
            for _ in range(3): self.assertTrue(p.search_places('q','c','s').ok)
            live.assert_not_called()

    def test_direct_result_shape_not_silently_dropped(self):
        with patch.object(scraper,'scrape_google_maps',return_value={'results':[{'business_name':'Fixture'},{'business_name':[]}]}):
            page = provider._scrape_direct('q','c','s',20)
        self.assertFalse(page.ok)
        self.assertEqual(page.error,'RESULT_PARSE_ERROR:PARSE')
        self.assertFalse(page.results)

    def test_untrusted_status_error_cannot_escape(self):
        page = provider._page_from_raw({'results':[],'status':SECRET,'error':SECRET},'q','c','s')
        self.assertEqual(page.status,'scrape_error')
        self.assertEqual(page.error,'UNKNOWN_PROVIDER_ERROR:PARSE')

    def test_cache_write_failure_is_unknown_outcome_not_success(self):
        page = provider._page_from_raw({'results':[]},'q','c','s')
        with tempfile.TemporaryDirectory() as td, patch.object(provider,'_scrape_direct',return_value=page), patch.object(provider,'_save_cache',side_effect=OSError(SECRET)):
            result = provider.BrowserMapsProvider(cache_dir=td,mode='direct').search_places('q','c','s')
        self.assertFalse(result.ok)
        self.assertEqual(result.error,'CACHE_WRITE_ERROR:CACHE_WRITE')

    def test_success_saved_to_instance_cache_and_replayed(self):
        page = provider._page_from_raw({'results':[{'business_name':'Fixture'}]},'q','c','s')
        with tempfile.TemporaryDirectory() as td, patch.object(provider,'_scrape_direct',return_value=page) as live:
            p = provider.BrowserMapsProvider(cache_dir=td,mode='direct')
            for _ in range(3): self.assertTrue(p.search_places('q','c','s').ok)
            self.assertEqual(live.call_count,1)
            self.assertEqual(len(list(Path(td).glob('*.json'))),1)


if __name__ == '__main__': unittest.main()
