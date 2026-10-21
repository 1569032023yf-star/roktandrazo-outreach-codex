"""Synthetic offline handoff contract regressions; no provider calls or DB."""
import copy
import unittest
from unittest.mock import patch

from brand_acquisition.dual_source_handoff import export_observations, validate_handoff


def observation(**changes):
    row = {"source": "osm", "provider_id": "node/1", "source_url": "https://www.openstreetmap.org/node/1",
           "captured_at": "2026-10-20T08:53:01Z", "name": "Synthetic Shop",
           "location": {"city": "Synthetic City"}, "site_candidate": "https://one.example/",
           "email_evidence": [], "package_sha256": "a" * 64}
    row.update(changes)
    return row


class HandoffTests(unittest.TestCase):
    def test_imported_authority_is_ignored_and_no_database_opened(self):
        with patch("sqlite3.connect", side_effect=AssertionError("DB forbidden")):
            payload = export_observations([observation(safe=True, history_status="SAFE", official_site_verified=True,
                                                       data_origin="live", identity_class="ORGANIZATION_CONFIRMED")])
        row = payload["candidates"][0]
        self.assertFalse(row["safe"])
        self.assertEqual(row["candidate"]["history_status"], "UNKNOWN")
        self.assertFalse(row["candidate"]["official_site_verified"])
        self.assertEqual(row["candidate"]["identity_class"], "IDENTITY_UNVERIFIED")
        self.assertEqual(row["candidate"]["data_origin"], "discovery_only")
        self.assertTrue(validate_handoff(payload))

    def test_same_source_id_retains_changed_capture(self):
        a = observation()
        b = observation(captured_at="2026-10-21T00:00:00Z", name="Changed name")
        payload = export_observations([a, a, b])
        self.assertEqual(len(payload["candidates"]), 1)
        self.assertEqual(len(payload["candidates"][0]["observations"]), 2)
        self.assertTrue(validate_handoff(payload))

    def test_cross_source_domain_only_potential_duplicate(self):
        payload = export_observations([observation(), observation(source="google", provider_id="place1",
                                      source_url="https://maps.google.com/?cid=1", site_candidate="https://www.one.example/contact")])
        self.assertEqual(len(payload["candidates"]), 2)
        for row in payload["candidates"]:
            self.assertEqual(len(row["potential_duplicates"]), 1)
        self.assertTrue(validate_handoff(payload))

    def test_same_name_different_domains_not_merged(self):
        payload = export_observations([observation(), observation(provider_id="node/2", site_candidate="https://two.example")])
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertTrue(all(not row["potential_duplicates"] for row in payload["candidates"]))

    def test_email_stays_evidence_not_qualified_business_email(self):
        evidence = {"email": "info@one.example", "source_url": "https://one.example/contact",
                    "excerpt": "Contact info@one.example", "captured_at": "2026-10-20T00:00:00Z"}
        payload = export_observations([observation(email_evidence=[evidence])])
        row = payload["candidates"][0]
        self.assertEqual(row["candidate"]["business_email"], "")
        self.assertEqual(row["observations"][0]["email_evidence"], [evidence])
        evidence["excerpt"] = "No matching address"
        with self.assertRaises(ValueError):
            export_observations([observation(email_evidence=[evidence])])

    def test_missing_provenance_rejected(self):
        for field in ["source", "provider_id", "source_url", "captured_at", "name", "location", "package_sha256"]:
            row = observation()
            del row[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                export_observations([row])

    def test_invalid_evidence_values_rejected(self):
        for change in [{"package_sha256": "bad"}, {"captured_at": "2026-10-20"},
                       {"location": {"latitude": float("nan")}}, {"site_candidate": "http://127.0.0.1/"},
                       {"source_url": "https://user:secret@example.com/"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                export_observations([observation(**change)])

    def test_export_tampering_rejected(self):
        payload = export_observations([observation()])
        for field, value in [("history_status", "SAFE"), ("official_site_verified", True), ("data_origin", "live")]:
            bad = copy.deepcopy(payload)
            bad["candidates"][0]["candidate"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_handoff(bad)
        bad = copy.deepcopy(payload)
        bad["candidates"][0]["safe"] = True
        with self.assertRaises(ValueError):
            validate_handoff(bad)

    def test_deterministic_order_and_input_preserved(self):
        rows = [observation(provider_id="node/2"), observation()]
        before = copy.deepcopy(rows)
        self.assertEqual(export_observations(rows), export_observations(list(reversed(rows))))
        self.assertEqual(rows, before)


if __name__ == "__main__":
    unittest.main()
