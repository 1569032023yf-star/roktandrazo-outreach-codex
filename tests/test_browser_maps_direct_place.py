import unittest
from discovery.providers.browser_maps_scraper import extract_direct_place_data

class Element:
    def __init__(self, text='', href=''): self.text, self.href = text, href
    def inner_text(self): return self.text
    def get_attribute(self, _): return self.href

class Page:
    def __init__(self, values): self.values = values
    def query_selector(self, selector): return self.values.get(selector)

class DirectPlaceTests(unittest.TestCase):
    def test_direct_place_is_one_candidate(self):
        p=Page({'h1':Element('Target Shop'),'[data-item-id="address"]':Element('1 Main St'),
                '[data-item-id^="phone"]':Element('607 555 0100'),'a[data-item-id="authority"]':Element(href='https://target.example/')})
        r=extract_direct_place_data(p,'https://www.google.com/maps/search/x')
        self.assertEqual(r['business_name'],'Target Shop'); self.assertEqual(r['website'],'https://target.example')
    def test_ambiguous_zero_card_is_not_candidate(self):
        self.assertIsNone(extract_direct_place_data(Page({'h1':Element('Google Maps')}),'https://www.google.com/maps/search/x'))
