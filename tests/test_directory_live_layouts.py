"""Minimal structural contracts extracted from captured public HTML."""
import unittest
from brand_acquisition.directory_adapters import parse_directory, DIRECTORY_SOURCES


class LiveLayoutTests(unittest.TestCase):
    def test_toyfair_country_rows_from_captured_tab(self):
        html = '''<h2>2026 PARTICIPATING RETAILERS</h2><div class="tab-content">
        <div id="1-f" class="tab-pane fade active show"><div class="row inner-tab-data">
        <p><strong>1/2 OFF CARDS</strong> (United States)<br>
        <strong>101 FUN PLUS LLC</strong> (United States)<br>
        <strong>1DI INC.</strong> (Canada)<br></p></div></div></div>'''
        rows = parse_directory('toyfair', html, DIRECTORY_SOURCES['toyfair']['url'])
        self.assertEqual({r.brand_name for r in rows}, {'1/2 OFF CARDS', '101 FUN PLUS LLC', '1DI INC.'})
        self.assertEqual({r.brand_name: r.organization_country for r in rows}['1DI INC.'], 'Canada')
        self.assertTrue(all(not r.official_site_candidates for r in rows))
        self.assertTrue(all(not r.organization_identity_verified for r in rows))

    def test_navigation_and_unscoped_strong_are_not_organizations(self):
        html = '<h2>2026 PARTICIPATING RETAILERS</h2><p><strong>Navigation</strong> (United States)<br></p>'
        self.assertEqual(parse_directory('toyfair', html, DIRECTORY_SOURCES['toyfair']['url']), [])

    def test_other_directory_cannot_reuse_toyfair_layout(self):
        html = '<div class="inner-tab-data"><p><strong>Navigation</strong> (United States)<br></p></div>'
        self.assertEqual(parse_directory('astra', html, DIRECTORY_SOURCES['astra']['url']), [])


if __name__ == '__main__':
    unittest.main()
