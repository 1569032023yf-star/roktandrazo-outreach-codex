"""Offline adversarial conversion acceptance, synthetic contacts never live evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from brand_acquisition.providers import PageResult
from brand_acquisition.site_conversion import (
    ConversionBudget, SearchEvidenceAdapter, SiteConversion, attributed_groups,
    candidate_url, conversion_metrics, identity_evidence,
    blocked_by_network_policy,
)


def record(name='Alpha Books', rid='one', source='toyfair', country='United States'):
    return {'brand_name':name, 'organization_name':name, 'directory_record_id':rid,
        'organization_country':country, 'source_platforms':[source], 'fixture_status':'synthetic_test'}


def search(rid='one', urls=None):
    return SearchEvidenceAdapter({rid:[{'query':'Alpha Books official', 'provider':'synthetic',
        'searched_at':'2026-10-14T00:00:00+00:00', 'status':'ok',
        'results':[{'url':u, 'verified':True, 'email':'invented@ignored.invalid'}
            for u in (urls or ['https://alpha.invalid/'])]}]})


class Fetch:
    def __init__(self, html=None, status='ok', origin='LIVE_PUBLIC_CAPTURE'):
        self.html = html or '<title>Alpha Books</title><h1>Alpha Books</h1><p>Bookstore NY 10011</p>'
        self.calls, self.status, self.origin = [], status, origin

    def fetch(self, url, **kwargs):
        self.calls.append(url)
        return PageResult(url,self.status,self.html,final_url=url,
            http_status=403 if self.status=='access_restricted' else 200,
            fetched_at='2026-10-14T00:00:00+00:00', content_type='text/html',
            data_origin=self.origin)


def extract(pages, name):
    # Contract stub: independent checks below must reject even faulty extractor.
    import re
    for p in pages:
        match = re.search(r'[\w.+-]+@[\w.-]+\.[a-z]+',p['text'])
        if match:
            email = match.group(0)
            return {'email':email,'snippet':email,'evidence':{'final_url':p['final_url']}}
    return {}


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def engine(self, fetch=None, adapter=None, records=None, **kwargs):
        return SiteConversion(records or [record()], adapter or search(), self.tmp.name, 'fixed-input',
            fetcher=fetch or Fetch(), extractor=extract,
            mx_checker=kwargs.pop('mx_checker',lambda d:{'has_mx':True,'provider':'other'}), **kwargs)

    def test_no_explicit_site_search_discovers_unverified_clue(self):
        clues, queries = search().discover(record())
        self.assertEqual(1,len(clues))
        self.assertNotIn('verified',clues[0])
        self.assertNotIn('email',clues[0])
        self.assertEqual('discovery_only',clues[0]['evidence_scope'])

    def test_wrong_identity_rejected(self):
        e = self.engine(Fetch('<title>Beta Toys</title><p>Alpha Books mentioned by a retailer; bookstore NY 10011</p>'))
        e.run()
        self.assertFalse(e.state['rows']['one']['official_site_verified'])

    def test_homonyms_different_domains_not_merged(self):
        rows = [self.verified('one','Alpha Books','https://alpha.invalid/'),self.verified('two','Alpha Books','https://other.invalid/')]
        groups, conflicts = attributed_groups(rows)
        self.assertEqual(2,len(groups))
        self.assertEqual({'one','two'},conflicts)
        self.assertEqual(0,conversion_metrics(rows)['OFFICIAL_SITES_VERIFIED'])

    def verified(self,rid,name,website,source='toyfair'):
        return {**record(name,rid,source), 'official_site_verified':True,'official_website':website,
            'website_identity':{'attributed_name':name.lower()},'business_email':'','history_status':'UNKNOWN',
            'validation_scope':'live_first_party'}

    def test_same_brand_multisource_evidence_groups(self):
        rows = [self.verified('one','Alpha Books','https://alpha.invalid/'),self.verified('two','Alpha Books','https://alpha.invalid/','nynow')]
        self.assertEqual(1,conversion_metrics(rows)['DUPLICATES_CONFIRMED'])
        self.assertEqual(2,len(rows))

    def test_parent_domain_different_brands_remain_separate(self):
        rows = [self.verified('one','Alpha Books','https://parent.invalid/'),self.verified('two','Beta Games','https://parent.invalid/')]
        self.assertEqual(2,len(attributed_groups(rows)[0]))

    def test_no_email_is_not_invented(self):
        e = self.engine()
        e.run()
        self.assertTrue(e.state['rows']['one']['official_site_verified'])
        self.assertEqual('',e.state['rows']['one']['business_email'])

    def test_third_party_email_rejected(self):
        f = Fetch('<title>Alpha Books</title><p>Bookstore NY 10011 sales@thirdparty.invalid</p>')
        e = self.engine(f)
        e.run()
        self.assertEqual('',e.state['rows']['one']['business_email'])
        self.assertEqual('official_domain_mismatch',e.state['rows']['one']['rejected_email_observations'][0]['reason'])

    def test_placeholder_rejected(self):
        f = Fetch('<title>Alpha Books</title><p>Bookstore NY 10011 yourname@alpha.invalid</p>')
        e = self.engine(f)
        e.run()
        self.assertEqual('',e.state['rows']['one']['business_email'])
        self.assertTrue(e.state['rows']['one']['rejected_email_observations'])

    def test_history_unknown_never_clean(self):
        f = Fetch('<title>Alpha Books</title><p>Bookstore NY 10011 sales@alpha.invalid</p>')
        m = self.engine(f).run()
        self.assertEqual(1,m['ENGINEERING_FIXTURE_EMAIL_VALIDATIONS'])
        self.assertEqual(0,m['FIRST_PARTY_EMAILS_FOUND'])
        self.assertEqual(0,m['HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL'])

    def test_mx_dns_error_never_passes(self):
        f = Fetch('<title>Alpha Books</title><p>Bookstore NY 10011 sales@alpha.invalid</p>')
        e = self.engine(f,mx_checker=lambda d:{'has_mx':True,'provider':'dns_error'})
        m = e.run()
        self.assertEqual('dns_error',e.state['rows']['one']['mx_status'])
        self.assertEqual(0,m['MX_OK'])

    def test_network_failure_checkpoint_survives(self):
        self.engine(Fetch(status='network_error')).run()
        state = json.loads((Path(self.tmp.name)/'checkpoint.json').read_text())
        self.assertEqual(1,state['rows']['one']['http_attempts'])
        self.assertEqual('network_error',state['request_log'][0]['status'])

    def test_restriction_stops_host_persistently(self):
        f = Fetch(status='access_restricted')
        e = self.engine(f)
        e.run(); e.run()
        self.assertEqual(1,len(f.calls))
        self.assertIn('alpha.invalid',e.state['stopped_hosts'])

    def test_rerun_idempotent_no_duplicate_customers(self):
        f = Fetch()
        e = self.engine(f)
        first = e.run(); second = e.run()
        self.assertEqual(first,second)
        self.assertEqual(1,len(f.calls))

    def test_country_mismatch_pending(self):
        e = self.engine(Fetch('<title>Alpha Books</title><p>Bookstore London United Kingdom</p>'))
        e.run()
        self.assertFalse(e.state['rows']['one']['official_site_verified'])

    def test_scripts_cannot_supply_identity_or_email(self):
        f = Fetch('<title>Beta Books</title><script>Alpha Books NY 10011 sales@alpha.invalid</script><p>Bookstore</p>')
        e = self.engine(f)
        e.run()
        self.assertFalse(e.state['rows']['one']['official_site_verified'])

    def test_imported_page_cannot_qualify(self):
        e = self.engine(Fetch(origin='AUTHORIZED_PUBLIC_IMPORT'))
        e.run()
        self.assertFalse(e.state['rows']['one']['official_site_verified'])
        self.assertFalse((Path(self.tmp.name)/'captures/capture_manifest.json').exists())

    def test_social_directory_private_candidates_rejected(self):
        for url in ['https://facebook.com/alpha','https://nynow.a2zinc.net/foo','https://127.0.0.1/','https://localhost/']:
            self.assertEqual('',candidate_url(url))

    def test_budget_bounds(self):
        with self.assertRaises(ValueError):
            ConversionBudget(http_workers=5)

    def test_mismatched_checkpoint_input_rejected(self):
        self.engine().run()
        with self.assertRaises(ValueError):
            SiteConversion([record()],search(),self.tmp.name,'another',extractor=extract)

    def test_third_party_product_title_cannot_impersonate_brand(self):
        f = Fetch('<title>Alpha Books products | Beta Retailer</title><p>Bookstore NY 10011 sales@alpha.invalid</p>')
        e = self.engine(f)
        e.run()
        self.assertFalse(e.state['rows']['one']['official_site_verified'])

    def test_secondary_title_segment_cannot_supply_site_identity(self):
        f = Fetch('<title>Beta Retailer | Alpha Books</title><p>Bookstore NY 10011 sales@alpha.invalid</p>')
        e = self.engine(f)
        e.run()
        self.assertFalse(e.state['rows']['one']['official_site_verified'])
        self.assertEqual('',e.state['rows']['one']['business_email'])

    def test_brand_logo_supports_display_name_alias(self):
        f = Fetch('<title>Alpha | Art of Books</title><a href="/" id="site-logo"><img class="logo" alt="Alpha Books Logo"></a><p>Bookstore NY 10011 sales@alpha.invalid</p>')
        e = self.engine(f)
        m = e.run()
        self.assertTrue(e.state['rows']['one']['official_site_verified'])
        self.assertEqual(0,m['OFFICIAL_SITES_VERIFIED'])
        self.assertEqual(1,m['ENGINEERING_FIXTURE_SITE_VALIDATIONS'])

    def test_challenge_200_stops_without_capture(self):
        f = Fetch('<title>One moment, please... Loader</title><p>Please wait while your request is being verified...</p>')
        e = self.engine(f)
        e.run(); e.run()
        self.assertEqual(1,len(f.calls))
        self.assertFalse((Path(self.tmp.name)/'captures/capture_manifest.json').exists())

    def test_network_policy_truthy_spellings(self):
        for value in ('1','true','YES',' on ',' True '):
            self.assertTrue(blocked_by_network_policy(value))
        self.assertFalse(blocked_by_network_policy('0'))

    def test_mx_recovery_does_not_refetch_site(self):
        f = Fetch('<title>Alpha Books</title><p>Bookstore NY 10011 sales@alpha.invalid</p>')
        e = self.engine(f,mx_checker=lambda d:{'has_mx':False,'provider':'dns_error'})
        e.run()
        e.mx_checker = lambda d:{'has_mx':True,'provider':'other'}
        e.run()
        self.assertEqual('ok',e.state['rows']['one']['mx_status'])
        self.assertEqual(1,len(f.calls))

    def test_changed_search_cannot_reset_cumulative_budget(self):
        e = self.engine(Fetch(status='network_error'))
        e.run()
        e.search.observations['one'][0]['query']='query 2'
        e.run()
        e.search.observations['one'][0]['query']='query 3'
        with self.assertRaisesRegex(ValueError,'cumulative search budget'):
            e.run()

    def test_callable_history_cannot_claim_available_copy(self):
        f = Fetch('<title>Alpha Books</title><p>Bookstore NY 10011 sales@alpha.invalid</p>')
        e = self.engine(f, history=lambda r:'new_candidate')
        e.run()
        self.assertFalse(e.state['rows']['one']['history_source_available'])
        self.assertEqual('UNKNOWN',e.state['rows']['one']['history_status'])

    def test_clean_metric_requires_available_history(self):
        row = self.verified('one','Alpha Books','https://alpha.invalid/')
        row.update(business_email='sales@alpha.invalid', email_hygiene_status='ok', mx_status='ok', history_status='new_candidate')
        self.assertEqual(0,conversion_metrics([row])['HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL'])
        row['history_source_available'] = True
        self.assertEqual(1,conversion_metrics([row])['HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL'])

    def test_host_budget_survives_changed_search(self):
        f = Fetch(status='network_error')
        e = self.engine(f, adapter=search(urls=['https://a.invalid/','https://b.invalid/','https://c.invalid/']))
        e.run()
        e.search.observations['one'][0]['query'] = 'query 2'
        e.search.observations['one'][0]['results'] = [{'url':'https://d.invalid/'}]
        e.run()
        self.assertNotIn('https://d.invalid/',f.calls)
        self.assertEqual(3,len(e.state['rows']['one']['attempted_hosts']))

    def test_checkpoint_reparses_logo_without_http(self):
        f = Fetch('<title>Alpha | Books</title><a href="/" id="site-logo"><img class="logo" alt="Alpha Books Logo"></a><p>Bookstore NY 10011</p>')
        e = self.engine(f)
        e.run()
        del e.state['rows']['one']['pages'][0]['logo_labels']
        e._save()
        resumed = self.engine(f)
        resumed.run()
        self.assertTrue(resumed.state['rows']['one']['official_site_verified'])
        self.assertEqual(['Alpha Books'],resumed.state['rows']['one']['pages'][0]['logo_labels'])
        self.assertEqual(1,len(f.calls))

    def test_third_party_logo_cannot_supply_site_identity(self):
        for logo in ('<img class="brand-logo" alt="Alpha Books Logo">',
            '<a href="/" id="site-logo"><img class="logo" alt="Alpha Books Logo"></a>'):
            pages = [{'requested_url':'https://beta.invalid/','final_url':'https://beta.invalid/',
                'text':'Bookstore NY 10011 sales@beta.invalid','page_title':'Beta Retailer',
                'logo_labels':['Alpha Books']}]
            self.assertFalse(identity_evidence(record(), pages)['verified'])
            f = Fetch('<title>Beta Retailer</title>'+logo+'<p>Bookstore NY 10011 sales@beta.invalid</p>')
            with tempfile.TemporaryDirectory() as output:
                e = SiteConversion([record()],search(),output,'fixed',fetcher=f,extractor=extract)
                e.run()
                self.assertFalse(e.state['rows']['one']['official_site_verified'])
                self.assertEqual('',e.state['rows']['one']['business_email'])

    def test_unavailable_history_clears_prior_clean_status(self):
        e = self.engine()
        e.run()
        e.state['rows']['one']['history_status'] = 'new_candidate'
        e._save()
        resumed = self.engine()
        resumed.run()
        self.assertEqual('UNKNOWN',resumed.state['rows']['one']['history_status'])


if __name__ == '__main__':
    unittest.main()
