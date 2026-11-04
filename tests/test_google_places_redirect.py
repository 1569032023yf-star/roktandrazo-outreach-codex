import io
import unittest
import urllib.request
import urllib.response
from email.message import Message
from unittest.mock import patch
from discovery.providers.google_places import GooglePlacesProvider, _RejectRedirect


class RedirectBoundaryTests(unittest.TestCase):
    def test_real_opener_rejects_all_redirects_without_second_request(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                calls = []
                class FakeHTTPS(urllib.request.HTTPSHandler):
                    def https_open(self, request):
                        calls.append(request)
                        headers = Message()
                        headers['Location'] = 'https://other.invalid/credential-target'
                        result = urllib.response.addinfourl(io.BytesIO(), headers, request.full_url, code)
                        result.msg = 'Redirect'
                        return result
                # Use the real urllib redirect/error pipeline without any sockets.
                opener = urllib.request.build_opener(FakeHTTPS(), _RejectRedirect())
                with patch('discovery.providers.google_places._open_request', side_effect=opener.open):
                    page = GooglePlacesProvider(api_key='fixture', min_interval_seconds=0).search_places('q', 'c', 'TN')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].get_method(), 'POST')
                self.assertEqual(calls[0].full_url, 'https://places.googleapis.com/v1/places:searchText')
                self.assertEqual(page.status, 'provider_outcome_unknown')
                self.assertEqual(page.request_count, 1)
                self.assertEqual(page.error, 'provider_transport_unknown_no_replay')


if __name__ == '__main__':
    unittest.main()
