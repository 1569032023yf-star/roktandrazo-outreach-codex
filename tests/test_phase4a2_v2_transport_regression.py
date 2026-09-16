"""V2 transport regression / V2 传输层回归：相同 MX 回应不得改变资格决策。"""
from __future__ import annotations

import unittest

from campaign_eligible_v2 import review_campaign_eligible_v2
from dev_fsp import materialize_dev_fsp
from discovery.discovery_service import DiscoveryService
from discovery.models import ProviderPage
from discovery.providers.mock_provider import MockPlacesProvider
from discovery.website_resolver import ProviderWebsiteResolver
from retail_city_queue import activate_next_city
from safe_replenishment import run_development_funnel
from tests.test_discovery_service import DiscoveryDb, MockFetcher, result
from tests.test_phase2b_safe_replenishment import StaticResolutionProvider, official_result


class V2TransportRegressionTests(unittest.TestCase):
    def test_current_safe_replenishment_fixture_has_zero_v2_policy_diff(self):
        """Routing may change, but the identical fixture and MX response must not."""
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            staged = result("Nashville Board Game Depot", result_id="phase4a2-v2", website="", email="")
            page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [staged])
            service = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page}))
            resolver = ProviderWebsiteResolver(StaticResolutionProvider([official_result()]))
            run_development_funnel(
                conn, service, city, resolver,
                MockFetcher({
                    "https://nashvilleboarddepot.com": "Nashville Board Game Depot official website",
                    "https://nashvilleboarddepot.com/contact": "Nashville Board Game Depot sales@nashvilleboarddepot.com",
                }),
                {"nashvilleboarddepot.com": "ok"}, "phase4a2-fixture",
            )
            lead = dict(conn.execute("SELECT * FROM leads").fetchone())
            context = {"conn": conn, "mx_lookup": {"nashvilleboarddepot.com": "ok"}}
            before = review_campaign_eligible_v2(lead, context)
            after = review_campaign_eligible_v2(lead, context)
            fields = ("tier", "eligible", "pool", "blockers", "mx_status")
            self.assertEqual({key: before[key] for key in fields}, {key: after[key] for key in fields})
            self.assertTrue(before["eligible"], before["blockers"])
            self.assertEqual(before["mx_status"], "ok")
            self.assertEqual(materialize_dev_fsp(conn, [lead["id"]], context["mx_lookup"], "phase4a2-fixture")["eligible"], 1)
