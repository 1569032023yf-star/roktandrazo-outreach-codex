"""Production-source compatibility regression / 生产源码兼容回归。 Offline only / 仅离线。"""
import importlib.util
import sys
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / 'patches/production/city_legacy_retry' / os.environ.get('CITY_RETRY_SOURCE', 'candidate')
import discovery
for name, relative in [('retail_city_queue','retail_city_queue.py'), ('discovery.discovery_service','discovery/discovery_service.py')]:
    spec = importlib.util.spec_from_file_location(name, CANDIDATE / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if name.startswith('discovery.'):
        discovery.discovery_service = module
import copy
import json
import unittest
from unittest.mock import Mock
from datetime import timedelta
from tests.test_city_network_recovery import CityNetworkRecoveryTests
from tests.test_discovery_service import DiscoveryDb
from retail_city_queue import automatic_recovery_deferred
import retail_city_queue
legacy_recovery_handoff_valid = getattr(retail_city_queue, "legacy_recovery_handoff_valid", None)

class LegacyCompatibilityTests(CityNetworkRecoveryTests):
    def test_linked_success_on_third_scan_follows_existing_evidence_gate(self):
        # Exact production baseline rejects this old fixture's identity; never loosen it.
        from tests import test_phase4a1b_linked_backlog as fixture
        from tests.test_city_network_recovery import TimeoutFetcher
        with DiscoveryDb() as conn:
            service,city,row,fetch,lead_id=fixture.LinkedBacklogTests().setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='review_recovery',review_reason_detail='review_recovery=official_site_unavailable' WHERE id=?",(lead_id,))
            conn.execute("UPDATE lead_discovery_results SET validation_status='review_recovery' WHERE id=?",(row['id'],))
            for _ in range(2):
                self.elapse();service.run_linked_backlog(city,Mock(),fetcher=TimeoutFetcher())
            self.elapse();summary=service.run_linked_backlog(city,Mock(),fetcher=fetch)
            self.assertEqual(summary['existing_leads_linked'],0)
            self.assertEqual(conn.execute('SELECT validation_status FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone()[0],'identity_review')

    def test_linked_legacy_quarantine_requires_original_identity_gate(self):
        from tests import test_phase4a1b_linked_backlog as fixture
        with DiscoveryDb() as conn:
            service,city,row,fetch,lead_id=fixture.LinkedBacklogTests().setup_case(conn)
            conn.execute('UPDATE lead_discovery_results SET raw_payload_json=? WHERE id=?',(json.dumps({'linked_backlog_retry':{'attempts':31}}),row['id']))
            conn.execute("UPDATE leads SET review_status='identity_review' WHERE id=?",(lead_id,))
            self.assertEqual(service.run_linked_backlog(city,Mock(),fetcher=fetch)['processed'],0)
            saved=dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone())
            self.assertNotIn('compatibility_handoff',json.loads(saved['raw_payload_json'])['linked_backlog_retry'])
            self.assertFalse(automatic_recovery_deferred(saved))
            conn.execute("UPDATE leads SET review_status='pending' WHERE id=?",(lead_id,))
            service.run_linked_backlog(city,Mock(),fetcher=fetch)
            saved=dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone())
            self.assertTrue(automatic_recovery_deferred(saved))

    def save_retry(self, conn, row, retry):
        conn.execute('UPDATE lead_discovery_results SET raw_payload_json=? WHERE id=?', (json.dumps({'provider_fact':'retained','website_resolution_retry':retry}),row['id']))
        return dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone())

    def test_legacy_31_missing_history_manual_idempotent_without_lead_change(self):
        with DiscoveryDb() as conn:
            service,city,row,_,lead_id=self.missing_website(conn)
            before=dict(conn.execute('SELECT * FROM leads WHERE id=?',(lead_id,)).fetchone())
            row=self.save_retry(conn,row,{'attempts':31})
            updated,changed=service._prepare_recovery_compatibility(row,'website_resolution_retry')
            self.assertTrue(changed)
            self.assertTrue(automatic_recovery_deferred(updated))
            retry=json.loads(updated['raw_payload_json'])['website_resolution_retry']
            self.assertEqual(retry['attempts'],31)
            self.assertNotIn('failures',retry)
            self.assertEqual(retry['compatibility_handoff']['legacy_retry'],{'attempts':31})
            self.assertFalse(service._prepare_recovery_compatibility(updated,'website_resolution_retry')[1])
            self.assertEqual(dict(conn.execute('SELECT * FROM leads WHERE id=?',(lead_id,)).fetchone()),before)
            resolver=Mock()
            self.assertEqual(service.run_website_resolution(city,resolver).results_seen,0)
            resolver.resolve.assert_not_called()
            for field in ('legacy_sha256','applied_at','action','schema_version'):
                forged=copy.deepcopy(retry);forged['compatibility_handoff'][field]='forged'
                self.assertFalse(legacy_recovery_handoff_valid(forged,'website_resolution_retry'))

    def test_20_attempts_one_real_failure_preserved_then_three_real_failures(self):
        with DiscoveryDb() as conn:
            service,city,row,_,_=self.missing_website(conn)
            row=dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone())
            service._record_network_failure(row,'website_resolution_retry','network_retry','TimeoutError:real')
            row=dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone())
            retry=json.loads(row['raw_payload_json'])['website_resolution_retry'];retry['attempts']=20
            row=self.save_retry(conn,row,retry)
            updated,changed=service._prepare_recovery_compatibility(row,'website_resolution_retry')
            self.assertTrue(changed)
            value=json.loads(updated['raw_payload_json'])['website_resolution_retry']
            self.assertEqual(value['attempts'],1);self.assertEqual(value['failures'],retry['failures'])
            self.assertFalse(automatic_recovery_deferred(updated))
            for expected in (2,3):
                self.elapse();service._record_network_failure(updated,'website_resolution_retry','network_retry','TimeoutError:real')
                updated=dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone())
                self.assertEqual(json.loads(updated['raw_payload_json'])['website_resolution_retry']['attempts'],expected)

    def test_migration_transaction_rollback_and_sql_failure(self):
        with DiscoveryDb() as conn:
            service,_,row,_,_=self.missing_website(conn)
            row=self.save_retry(conn,row,{'attempts':31});conn.commit()
            original=row['raw_payload_json']
            service._prepare_recovery_compatibility(row,'website_resolution_retry')
            self.assertTrue(conn.in_transaction);conn.rollback()
            self.assertEqual(conn.execute('SELECT raw_payload_json FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone()[0],original)
            conn.execute("CREATE TEMP TRIGGER fail_legacy BEFORE UPDATE ON lead_discovery_results BEGIN SELECT RAISE(ABORT,'offline test'); END")
            with self.assertRaises(Exception):service._prepare_recovery_compatibility(row,'website_resolution_retry')
            self.assertEqual(conn.execute('SELECT raw_payload_json FROM lead_discovery_results WHERE id=?',(row['id'],)).fetchone()[0],original)

def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(LegacyCompatibilityTests)

if __name__ == '__main__':unittest.main()
